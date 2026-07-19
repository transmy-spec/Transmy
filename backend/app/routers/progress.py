# ruff: noqa: E501, E701, E702
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

router = APIRouter(prefix="/api/v1", tags=["personalized progress"])


class GoalInput(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    success_criteria: str = Field(default="", max_length=2000)
    person_feedback: str = Field(default="", max_length=2000)
    status: Literal["planned", "in_progress", "achieved", "adapted", "abandoned"] = "planned"
    progress: int = Field(default=0, ge=0, le=100)
    target_date: date | None = None


class ReviewInput(BaseModel):
    summary: str = Field(min_length=3, max_length=5000)
    next_steps: str = Field(default="", max_length=3000)
    attendee_ids: list[UUID] = Field(default_factory=list, max_length=50)


def _audit(connection: Any, context: SecurityContext, event: str, target: UUID, target_type: str) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id,actor_user_id,event_type,target_type,target_id,metadata) VALUES
      (:organization_id,:user_id,:event,:target_type,:target,CAST(:metadata AS jsonb))"""),
      {**_person_params(context), "event": event, "target_type": target_type,
       "target": target, "metadata": json.dumps({})})


@router.get("/people/{person_id}/personalized-goals")
def list_goals(person_id: UUID, context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "personalized_plan.read")
    with engine.begin() as connection:
        rows = connection.execute(text("""SELECT g.* FROM app.personalized_goal g
          JOIN app.personalized_plan p ON p.id=g.plan_id WHERE p.person_id=:person_id
          AND p.organization_id=:organization_id AND p.status IN ('draft','active')
          AND EXISTS(SELECT 1 FROM app.person_assignment pa JOIN app.membership m ON m.unit_id=pa.unit_id
            WHERE pa.person_id=p.person_id AND m.user_id=:user_id AND pa.ends_at IS NULL AND m.ends_at IS NULL)
          ORDER BY g.target_date NULLS LAST,g.created_at"""),
          {**_person_params(context), "person_id": person_id}).mappings()
        items = []
        for row in rows:
            item = dict(row); item.update(decrypt_json(item.pop("encrypted_payload"), item["id"].bytes)); items.append(item)
        _audit(connection, context, "personalized_goal.listed", person_id, "supported_person")
    return {"items": items}


@router.post("/people/{person_id}/personalized-goals", status_code=201)
def create_goal(person_id: UUID, payload: GoalInput, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "personalized_plan.manage"); verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    goal_id = uuid4(); encrypted = encrypt_json({"title": payload.title.strip(), "success_criteria": payload.success_criteria.strip(), "person_feedback": payload.person_feedback.strip()}, goal_id.bytes)
    with engine.begin() as connection:
        plan = connection.execute(text("""SELECT p.id FROM app.personalized_plan p WHERE p.person_id=:person_id
          AND p.organization_id=:organization_id AND p.status IN ('draft','active')
          AND EXISTS(SELECT 1 FROM app.person_assignment pa JOIN app.membership m ON m.unit_id=pa.unit_id
            WHERE pa.person_id=p.person_id AND m.user_id=:user_id AND pa.ends_at IS NULL AND m.ends_at IS NULL)
          ORDER BY p.created_at DESC LIMIT 1"""), {**_person_params(context), "person_id": person_id}).first()
        if not plan: raise HTTPException(status.HTTP_404_NOT_FOUND, "plan_not_found")
        connection.execute(text("""INSERT INTO app.personalized_goal
          (id,plan_id,status,progress,target_date,encrypted_payload,created_by,updated_by)
          VALUES(:id,:plan,:status,:progress,:target,:payload,:user_id,:user_id)"""),
          {**_person_params(context), "id": goal_id, "plan": plan[0], "status": payload.status,
           "progress": payload.progress, "target": payload.target_date, "payload": encrypted})
        _audit(connection, context, "personalized_goal.created", goal_id, "personalized_goal")
    response.headers["ETag"] = _etag(1); return {"id": goal_id, "row_version": 1}


@router.put("/people/{person_id}/personalized-goals/{goal_id}")
def update_goal(person_id: UUID, goal_id: UUID, payload: GoalInput, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> dict[str, Any]:
    require_permission(context, "personalized_plan.manage"); verify_csrf(request, context, request.headers.get("X-CSRF-Token")); expected = _parse_if_match(if_match)
    encrypted = encrypt_json({"title": payload.title.strip(), "success_criteria": payload.success_criteria.strip(), "person_feedback": payload.person_feedback.strip()}, goal_id.bytes)
    with engine.begin() as connection:
        updated = connection.execute(text("""UPDATE app.personalized_goal g SET status=:status,progress=:progress,
          target_date=:target,encrypted_payload=:payload,updated_by=:user_id,updated_at=now(),row_version=row_version+1
          FROM app.personalized_plan p WHERE g.id=:id AND g.plan_id=p.id AND p.person_id=:person_id
          AND p.organization_id=:organization_id AND g.row_version=:version RETURNING g.*"""),
          {**_person_params(context), "id": goal_id, "person_id": person_id, "status": payload.status,
           "progress": payload.progress, "target": payload.target_date, "payload": encrypted, "version": expected}).mappings().first()
        if not updated: raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "personalized_goal.updated", goal_id, "personalized_goal")
    response.headers["ETag"] = _etag(updated["row_version"]); return dict(updated)


@router.post("/schedule/{entry_id}/review", status_code=201)
def review_event(entry_id: UUID, payload: ReviewInput, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "schedule.event.create"); verify_csrf(request, context, request.headers.get("X-CSRF-Token")); review_id = uuid4()
    encrypted = encrypt_json({"summary": payload.summary.strip(), "next_steps": payload.next_steps.strip()}, review_id.bytes)
    with engine.begin() as connection:
        event = connection.execute(text("""SELECT e.id FROM app.schedule_entry e WHERE e.id=:id
          AND e.organization_id=:organization_id AND e.entry_type='event' AND e.created_by=:user_id"""),
          {**_person_params(context), "id": entry_id}).first()
        if not event: raise HTTPException(status.HTTP_404_NOT_FOUND, "event_not_found")
        connection.execute(text("""INSERT INTO app.schedule_review(id,entry_id,encrypted_payload,created_by)
          VALUES(:id,:entry,:payload,:user_id)"""), {"id": review_id, "entry": entry_id,
          "payload": encrypted, "user_id": context.user_id})
        for person_id in set(payload.attendee_ids):
            connection.execute(text("""INSERT INTO app.schedule_attendance(review_id,person_id,attended)
              SELECT :review,sp.person_id,true FROM app.schedule_person sp
              WHERE sp.entry_id=:entry AND sp.person_id=:person"""),
              {"review": review_id, "entry": entry_id, "person": person_id})
        _audit(connection, context, "schedule.review_created", review_id, "schedule_review")
    return {"id": review_id, "row_version": 1}
