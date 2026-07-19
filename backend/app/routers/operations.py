import csv
import hashlib
import io
import json
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.routers.people import _etag, _parse_if_match, _person_params
from app.security import (
    SecurityContext,
    get_security_context,
    random_token,
    require_permission,
    token_hash,
    verify_csrf,
)

router = APIRouter(prefix="/api/v1", tags=["retention and exports"])


class ExportInput(BaseModel):
    export_type: Literal["activity_summary", "audit_log"]
    format: Literal["json", "csv"] = "json"
    reason: str = Field(min_length=5, max_length=500)


class PolicyInput(BaseModel):
    retention_days: int | None = Field(default=None, ge=1, le=36500)
    legal_basis: str | None = Field(default=None, max_length=500)
    status: Literal["pilot_pending", "disabled"] = "pilot_pending"


def _audit(connection: Any, context: SecurityContext, event: str, target: UUID | None) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id, actor_user_id, event_type, target_type, target_id, metadata)
      VALUES (:organization_id,:user_id,:event,'export',:target,CAST(:metadata AS jsonb))"""),
      {**_person_params(context), "event": event, "target": target,
       "metadata": json.dumps({})})


@router.get("/retention-policies")
def retention_policies(response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "retention.read")
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(text(
            "SELECT * FROM app.retention_policy ORDER BY data_type")).mappings()]
    response.headers["ETag"] = _etag(max((row["row_version"] for row in rows), default=1))
    return {"items": rows, "purge_engine_enabled": False}


@router.put("/retention-policies/{data_type}")
def update_retention(data_type: str, payload: PolicyInput, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> dict[str, Any]:
    require_permission(context, "retention.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        updated = connection.execute(text("""UPDATE app.retention_policy
          SET retention_days=:days, legal_basis=:basis, status=:status, purge_enabled=false,
              updated_by=:user_id, updated_at=now(), row_version=row_version+1
          WHERE data_type=:data_type AND row_version=:expected RETURNING *"""),
          {"days": payload.retention_days, "basis": payload.legal_basis,
           "status": payload.status, "user_id": context.user_id,
           "data_type": data_type, "expected": expected}).mappings().first()
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "retention.policy_updated", None)
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)


def _export_rows(connection: Any, context: SecurityContext, kind: str) -> list[dict[str, Any]]:
    if kind == "activity_summary":
        return [dict(row) for row in connection.execute(text("""SELECT u.name AS unit,
          (SELECT count(*) FROM app.supported_person p JOIN app.person_assignment pa
           ON pa.person_id=p.id WHERE pa.unit_id=u.id AND p.status='active') AS active_people,
          (SELECT count(*) FROM app.transmission t WHERE t.unit_id=u.id
           AND t.status='published') AS published_transmissions,
          (SELECT count(*) FROM app.task t WHERE t.unit_id=u.id
           AND t.status IN ('todo','in_progress')) AS open_tasks
          FROM app.unit u JOIN app.service s ON s.id=u.service_id
          JOIN app.establishment e ON e.id=s.establishment_id
          WHERE e.organization_id=:organization_id ORDER BY u.name"""),
          _person_params(context)).mappings()]
    return [dict(row) for row in connection.execute(text("""SELECT event_type,target_type,
      target_id,occurred_at FROM audit.event WHERE organization_id=:organization_id
      ORDER BY occurred_at DESC LIMIT 1000"""), _person_params(context)).mappings()]


@router.post("/exports", status_code=status.HTTP_201_CREATED)
def create_export(payload: ExportInput, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "export.request")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    export_id = uuid4()
    with engine.begin() as connection:
        rows = _export_rows(connection, context, payload.export_type)
        canonical = json.dumps(rows, default=str, ensure_ascii=True, sort_keys=True)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        connection.execute(text("""INSERT INTO app.export_request
          (id,organization_id,requested_by,export_type,format,reason,result_payload,
           record_count,sha256,expires_at) VALUES
          (:id,:organization_id,:user_id,:type,:format,:reason,CAST(:payload AS jsonb),
           :count,:sha256,now()+interval '15 minutes')"""),
          {**_person_params(context), "id": export_id, "type": payload.export_type,
           "format": payload.format, "reason": payload.reason.strip(), "payload": canonical,
           "count": len(rows), "sha256": digest})
        _audit(connection, context, "export.created", export_id)
    return {"id": str(export_id), "status": "ready", "record_count": len(rows),
            "sha256": digest, "expires_in_seconds": 900}


@router.get("/exports/{export_id}")
def get_export(export_id: UUID,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "export.request")
    with engine.connect() as connection:
        row = connection.execute(text("""SELECT id,export_type,format,status,record_count,
          sha256,created_at,expires_at,downloaded_at FROM app.export_request
          WHERE id=:id AND organization_id=:organization_id AND requested_by=:user_id"""),
          {**_person_params(context), "id": export_id}).mappings().first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return dict(row)


@router.post("/exports/{export_id}/download-ticket")
def create_download_ticket(export_id: UUID, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "export.download")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    token = random_token()
    with engine.begin() as connection:
        export = connection.execute(text("""SELECT id FROM app.export_request WHERE id=:id
          AND organization_id=:organization_id AND requested_by=:user_id
          AND status='ready' AND expires_at>now()"""),
          {**_person_params(context), "id": export_id}).first()
        if not export:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(text("""INSERT INTO app.export_download_ticket
          (id,export_id,token_hash,created_by,expires_at)
          VALUES (:id,:export_id,:hash,:user_id,now()+interval '2 minutes')"""),
          {"id": uuid4(), "export_id": export_id, "hash": token_hash(token),
           "user_id": context.user_id})
    return {"ticket": token, "download_url": f"/api/v1/export-downloads/{token}",
            "expires_in_seconds": 120}


@router.get("/export-downloads/{ticket}")
def download_export(ticket: str,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> Response:
    require_permission(context, "export.download")
    with engine.begin() as connection:
        row = connection.execute(text("""UPDATE app.export_download_ticket t SET used_at=now()
          FROM app.export_request e WHERE t.export_id=e.id AND t.token_hash=:hash
          AND t.used_at IS NULL AND t.expires_at>now() AND e.expires_at>now()
          AND e.requested_by=:user_id RETURNING e.id,e.format,e.result_payload"""),
          {"hash": token_hash(ticket), "user_id": context.user_id}).mappings().first()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(text("UPDATE app.export_request SET downloaded_at=now() WHERE id=:id"),
                           {"id": row["id"]})
        _audit(connection, context, "export.downloaded", row["id"])
    if row["format"] == "json":
        return JSONResponse(row["result_payload"], headers={"Cache-Control": "no-store"})
    output = io.StringIO()
    rows = row["result_payload"]
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=export.csv",
            "Cache-Control": "no-store",
        },
    )
