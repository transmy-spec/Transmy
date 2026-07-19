# ruff: noqa: E501
import json
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.routers.people import _etag, _parse_if_match, _person_params
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1/pilot-issues", tags=["pilot issues"])


class IssueCreate(BaseModel):
    acceptance_code: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=3000)
    severity: Literal["minor", "major", "critical"]
    assigned_to: UUID | None = None


class IssueUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "accepted"]
    assigned_to: UUID | None = None


def _audit(connection: Any, context: SecurityContext, event: str, target: UUID) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id,actor_user_id,event_type,target_type,target_id,metadata) VALUES
      (:organization_id,:user_id,:event,'pilot_issue',:target,CAST(:metadata AS jsonb))"""),
      {**_person_params(context), "event": event, "target": target, "metadata": json.dumps({})})


@router.get("")
def list_issues(context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "pilot_issue.read")
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(text("""SELECT i.*,a.title AS scenario_title,
          creator.display_name AS creator_name,assignee.display_name AS assignee_name
          FROM app.pilot_issue i LEFT JOIN app.acceptance_scenario a ON a.code=i.acceptance_code
          JOIN app.user_account creator ON creator.id=i.created_by
          LEFT JOIN app.user_account assignee ON assignee.id=i.assigned_to
          WHERE i.organization_id=:organization_id
          ORDER BY CASE i.severity WHEN 'critical' THEN 0 WHEN 'major' THEN 1 ELSE 2 END,i.created_at DESC"""),
          _person_params(context)).mappings()]
    open_items = [row for row in rows if row["status"] in ("open", "in_progress")]
    return {"items": rows, "summary": {"open": len(open_items),
      "critical": sum(row["severity"] == "critical" for row in open_items)}}


@router.post("", status_code=201)
def create_issue(payload: IssueCreate, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "pilot_issue.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    issue_id = uuid4()
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO app.pilot_issue
          (id,organization_id,acceptance_code,title,description,severity,created_by,assigned_to)
          VALUES (:id,:organization_id,:acceptance,:title,:description,:severity,:user_id,:assigned)"""),
          {**_person_params(context), "id": issue_id, "acceptance": payload.acceptance_code,
           "title": payload.title.strip(), "description": payload.description.strip(),
           "severity": payload.severity, "assigned": payload.assigned_to})
        _audit(connection, context, "pilot_issue.created", issue_id)
    return {"id": issue_id, **payload.model_dump(), "status": "open", "row_version": 1}


@router.put("/{issue_id}")
def update_issue(issue_id: UUID, payload: IssueUpdate, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> dict[str, Any]:
    require_permission(context, "pilot_issue.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        updated = connection.execute(text("""UPDATE app.pilot_issue SET status=:status,
          assigned_to=:assigned,updated_at=now(),row_version=row_version+1,
          resolved_at=CASE WHEN :status IN ('resolved','accepted') THEN now() ELSE NULL END,
          resolved_by=CASE WHEN :status IN ('resolved','accepted') THEN :user_id ELSE NULL END
          WHERE id=:id AND organization_id=:organization_id AND row_version=:version RETURNING *"""),
          {**_person_params(context), "id": issue_id, "status": payload.status,
           "assigned": payload.assigned_to, "version": expected}).mappings().first()
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "pilot_issue.updated", issue_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)
