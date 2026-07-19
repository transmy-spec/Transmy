# ruff: noqa: E501
import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.routers.people import _etag, _parse_if_match, _person_params
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1/acceptance", tags=["pilot acceptance"])


class AcceptanceInput(BaseModel):
    status: Literal["pending", "passed", "failed", "blocked"]
    notes: str = Field(default="", max_length=2000)


@router.get("")
def list_acceptance(context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "acceptance.read")
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(text("""SELECT s.*,u.display_name AS tester_name
          FROM app.acceptance_scenario s LEFT JOIN app.user_account u ON u.id=s.tested_by
          ORDER BY s.sort_order""")).mappings()]
    passed = sum(row["status"] == "passed" for row in rows)
    return {"items": rows, "summary": {"passed": passed, "total": len(rows),
      "complete": passed == len(rows), "failed": sum(row["status"] == "failed" for row in rows)}}


@router.put("/{code}")
def update_acceptance(code: str, payload: AcceptanceInput, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> dict[str, Any]:
    require_permission(context, "acceptance.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        updated = connection.execute(text("""UPDATE app.acceptance_scenario SET status=:status,
          notes=:notes,tested_by=:user_id,tested_at=now(),row_version=row_version+1
          WHERE code=:code AND row_version=:version RETURNING *"""),
          {"status": payload.status, "notes": payload.notes.strip(), "user_id": context.user_id,
           "code": code, "version": expected}).mappings().first()
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        connection.execute(text("""INSERT INTO audit.event
          (organization_id,actor_user_id,event_type,target_type,metadata) VALUES
          (:organization_id,:user_id,'acceptance.scenario_updated','acceptance',CAST(:metadata AS jsonb))"""),
          {**_person_params(context), "metadata": json.dumps({"code": code, "status": payload.status})})
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)
