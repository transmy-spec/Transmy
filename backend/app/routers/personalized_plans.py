# ruff: noqa: E501, S608
import json
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.crypto import decrypt_json, encrypt_json
from app.database import engine
from app.routers.people import _etag, _parse_if_match, _person_params
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1", tags=["personalized plans"])


class PlanContent(BaseModel):
    person_expectations: str = Field(min_length=1, max_length=5000)
    strengths: str = Field(default="", max_length=5000)
    assessed_needs: str = Field(default="", max_length=5000)
    goals: list[str] = Field(min_length=1, max_length=20)
    actions: list[str] = Field(default_factory=list, max_length=30)
    participation_method: str = Field(min_length=1, max_length=2000)
    consent_status: Literal["obtained", "refused", "unable"]
    consent_details: str = Field(default="", max_length=2000)
    representative_name: str = Field(default="", max_length=200)


class PlanInput(BaseModel):
    content: PlanContent
    review_due_at: date | None = None
    publish: bool = False


def _scope_sql() -> str:
    return """EXISTS (SELECT 1 FROM app.person_assignment pa JOIN app.membership m ON m.unit_id=pa.unit_id
      WHERE pa.person_id=:person_id AND m.user_id=:user_id AND pa.starts_at<=now()
      AND (pa.ends_at IS NULL OR pa.ends_at>now()) AND m.starts_at<=now()
      AND (m.ends_at IS NULL OR m.ends_at>now()))"""


def _audit(connection: Any, context: SecurityContext, event: str, plan_id: UUID, person_id: UUID) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id,actor_user_id,event_type,target_type,target_id,metadata) VALUES
      (:organization_id,:user_id,:event,'personalized_plan',:target,CAST(:metadata AS jsonb))"""),
      {**_person_params(context), "event": event, "target": plan_id,
       "metadata": json.dumps({"person_id": str(person_id)})})


def _result(row: dict[str, Any]) -> dict[str, Any]:
    payload = decrypt_json(row.pop("encrypted_payload"), UUID(str(row["id"])).bytes)
    return {**row, "content": payload}


@router.get("/people/{person_id}/personalized-plan")
def get_plan(person_id: UUID,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "personalized_plan.read")
    with engine.begin() as connection:
        row = connection.execute(text(f"""SELECT p.*,v.encrypted_payload,v.version_number,
          u.display_name AS author_name FROM app.personalized_plan p
          JOIN LATERAL (SELECT * FROM app.personalized_plan_version WHERE plan_id=p.id
            ORDER BY version_number DESC LIMIT 1) v ON true
          JOIN app.user_account u ON u.id=v.created_by WHERE p.person_id=:person_id
          AND p.organization_id=:organization_id AND {_scope_sql()}
          ORDER BY p.created_at DESC LIMIT 1"""), {**_person_params(context), "person_id": person_id}).mappings().first()
        if not row:
            return {"item": None}
        result = _result(dict(row))
        versions = [dict(item) for item in connection.execute(text("""SELECT v.version_number,
          v.created_at,u.display_name AS author_name FROM app.personalized_plan_version v
          JOIN app.user_account u ON u.id=v.created_by WHERE v.plan_id=:plan_id
          ORDER BY v.version_number DESC"""), {"plan_id": result["id"]}).mappings()]
        events = [dict(item) for item in connection.execute(text("""SELECT e.id,e.label,
          e.starts_at,e.ends_at,e.status FROM app.schedule_plan sp
          JOIN app.schedule_entry e ON e.id=sp.entry_id WHERE sp.plan_id=:plan_id
          ORDER BY e.starts_at DESC LIMIT 50"""), {"plan_id": result["id"]}).mappings()]
        _audit(connection, context, "personalized_plan.viewed", result["id"], person_id)
    return {"item": result, "versions": versions, "linked_events": events}


@router.post("/people/{person_id}/personalized-plan", status_code=201)
def create_plan(person_id: UUID, payload: PlanInput, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "personalized_plan.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    plan_id, version_id = uuid4(), uuid4()
    encrypted = encrypt_json(payload.content.model_dump(), plan_id.bytes)
    with engine.begin() as connection:
        allowed = connection.execute(text(f"SELECT 1 WHERE {_scope_sql()}"),
          {**_person_params(context), "person_id": person_id}).first()
        if not allowed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "person_not_found")
        connection.execute(text("""INSERT INTO app.personalized_plan
          (id,organization_id,person_id,status,review_due_at,created_by) VALUES
          (:id,:organization_id,:person_id,:status,:review_due_at,:user_id)"""),
          {**_person_params(context), "id": plan_id, "person_id": person_id,
           "status": "active" if payload.publish else "draft", "review_due_at": payload.review_due_at})
        connection.execute(text("""INSERT INTO app.personalized_plan_version
          (id,plan_id,version_number,encrypted_payload,created_by) VALUES (:id,:plan_id,1,:payload,:user_id)"""),
          {"id": version_id, "plan_id": plan_id, "payload": encrypted, "user_id": context.user_id})
        _audit(connection, context, "personalized_plan.created", plan_id, person_id)
    response.headers["ETag"] = _etag(1)
    return {"id": plan_id, "status": "active" if payload.publish else "draft", "row_version": 1}


@router.put("/people/{person_id}/personalized-plan/{plan_id}")
def update_plan(person_id: UUID, plan_id: UUID, payload: PlanInput, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> dict[str, Any]:
    require_permission(context, "personalized_plan.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    encrypted = encrypt_json(payload.content.model_dump(), plan_id.bytes)
    with engine.begin() as connection:
        updated = connection.execute(text(f"""UPDATE app.personalized_plan SET
          status=CASE WHEN :publish THEN 'active' ELSE status END,review_due_at=:review_due_at,
          updated_at=now(),row_version=row_version+1 WHERE id=:id AND person_id=:person_id
          AND organization_id=:organization_id AND row_version=:version AND {_scope_sql()}
          RETURNING *"""), {**_person_params(context), "id": plan_id, "person_id": person_id,
          "publish": payload.publish, "review_due_at": payload.review_due_at, "version": expected}).mappings().first()
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        connection.execute(text("""INSERT INTO app.personalized_plan_version
          (id,plan_id,version_number,encrypted_payload,created_by) VALUES
          (:id,:plan_id,:version,:payload,:user_id)"""), {"id": uuid4(), "plan_id": plan_id,
          "version": expected + 1, "payload": encrypted, "user_id": context.user_id})
        _audit(connection, context, "personalized_plan.updated", plan_id, person_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return {"id": plan_id, "status": updated["status"], "row_version": updated["row_version"]}
