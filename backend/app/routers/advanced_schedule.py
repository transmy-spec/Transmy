# ruff: noqa: E501
import json
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text

from app.database import engine
from app.routers.people import _etag, _parse_if_match, _person_params
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1/schedule", tags=["advanced team schedule"])


class InvitationResponse(BaseModel):
    response: Literal["accepted", "declined"]


class EventUpdate(BaseModel):
    label: str = Field(min_length=3, max_length=120)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def valid_period(self) -> "EventUpdate":
        if self.ends_at <= self.starts_at or self.ends_at > self.starts_at + timedelta(days=7):
            raise ValueError("invalid period")
        return self


class LeaveRequest(BaseModel):
    unit_id: UUID
    starts_at: datetime
    ends_at: datetime
    leave_type: Literal["paid_leave", "training", "sick_leave", "recovery", "other"]

    @model_validator(mode="after")
    def valid_period(self) -> "LeaveRequest":
        if self.ends_at <= self.starts_at or self.ends_at > self.starts_at + timedelta(days=31):
            raise ValueError("invalid period")
        return self


class LeaveDecision(BaseModel):
    decision: Literal["approved", "rejected"]


def _audit(connection: Any, context: SecurityContext, event: str, target: UUID,
    metadata: dict[str, Any] | None = None) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id,actor_user_id,event_type,target_type,target_id,metadata) VALUES
      (:organization_id,:user_id,:event,'schedule_entry',:target,CAST(:metadata AS jsonb))"""),
      {**_person_params(context), "event": event, "target": target,
       "metadata": json.dumps(metadata or {})})


@router.post("/{entry_id}/invitation-response")
def respond_invitation(entry_id: UUID, payload: InvitationResponse, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "schedule.event.create")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        updated = connection.execute(text("""UPDATE app.schedule_participant sp SET
          response_status=:response,responded_at=now() FROM app.schedule_entry e
          WHERE sp.entry_id=e.id AND sp.entry_id=:id AND sp.user_id=:user_id
          AND e.organization_id=:organization_id AND e.status='active' RETURNING sp.response_status"""),
          {**_person_params(context), "id": entry_id, "response": payload.response}).first()
        if not updated:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "invitation_not_found")
        _audit(connection, context, "schedule.invitation_responded", entry_id,
          {"response": payload.response})
    return {"response_status": payload.response}


@router.put("/{entry_id}/event")
def update_event(entry_id: UUID, payload: EventUpdate, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> dict[str, Any]:
    require_permission(context, "schedule.event.create")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        conflict = connection.execute(text("""SELECT 1 FROM app.schedule_participant mine
          JOIN app.schedule_participant other ON other.user_id=mine.user_id
          JOIN app.schedule_entry e ON e.id=other.entry_id WHERE mine.entry_id=:id
          AND other.entry_id<>:id AND e.status='active' AND e.entry_type IN ('event','absence')
          AND e.starts_at<:ends AND e.ends_at>:starts LIMIT 1"""),
          {"id": entry_id, "starts": payload.starts_at, "ends": payload.ends_at}).first()
        if conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, "participant_schedule_conflict")
        updated = connection.execute(text("""UPDATE app.schedule_entry SET label=:label,
          starts_at=:starts,ends_at=:ends,updated_at=now(),row_version=row_version+1
          WHERE id=:id AND organization_id=:organization_id AND created_by=:user_id
          AND entry_type='event' AND row_version=:version RETURNING *"""),
          {**_person_params(context), "id": entry_id, "label": payload.label.strip(),
           "starts": payload.starts_at, "ends": payload.ends_at, "version": expected}).mappings().first()
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "schedule.event_updated", entry_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)


@router.post("/leave-requests", status_code=201)
def request_leave(payload: LeaveRequest, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "leave.request")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    entry_id = uuid4()
    with engine.begin() as connection:
        eligible = connection.execute(text("""SELECT 1 FROM app.membership m JOIN app.unit u ON u.id=m.unit_id
          JOIN app.service s ON s.id=u.service_id JOIN app.establishment e ON e.id=s.establishment_id
          WHERE m.user_id=:user_id AND m.unit_id=:unit_id AND e.organization_id=:organization_id
          AND m.starts_at<=now() AND (m.ends_at IS NULL OR m.ends_at>now())"""),
          {**_person_params(context), "unit_id": payload.unit_id}).first()
        if not eligible:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "unit_not_found")
        overlap = connection.execute(text("""SELECT 1 FROM app.schedule_entry WHERE user_id=:user_id
          AND status='active' AND approval_status<>'rejected' AND entry_type='absence'
          AND starts_at<:ends AND ends_at>:starts"""),
          {"user_id": context.user_id, "starts": payload.starts_at, "ends": payload.ends_at}).first()
        if overlap:
            raise HTTPException(status.HTTP_409_CONFLICT, "leave_overlap")
        connection.execute(text("""INSERT INTO app.schedule_entry
          (id,organization_id,unit_id,user_id,entry_type,starts_at,ends_at,label,status,
           approval_status,created_by) VALUES (:id,:organization_id,:unit_id,:user_id,'absence',
           :starts,:ends,:label,'active','pending',:user_id)"""),
          {**_person_params(context), "id": entry_id, "unit_id": payload.unit_id,
           "starts": payload.starts_at, "ends": payload.ends_at,
           "label": payload.leave_type})
        _audit(connection, context, "leave.requested", entry_id,
          {"leave_type": payload.leave_type})
    return {"id": entry_id, "approval_status": "pending", "row_version": 1}


@router.post("/{entry_id}/leave-decision")
def decide_leave(entry_id: UUID, payload: LeaveDecision, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> dict[str, Any]:
    require_permission(context, "leave.approve")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        updated = connection.execute(text("""UPDATE app.schedule_entry e SET approval_status=:decision,
          reviewed_by=:user_id,reviewed_at=now(),updated_at=now(),row_version=row_version+1
          WHERE e.id=:id AND e.organization_id=:organization_id AND e.entry_type='absence'
          AND e.approval_status='pending' AND e.row_version=:version
          AND EXISTS(SELECT 1 FROM app.membership m WHERE m.user_id=:user_id AND m.unit_id=e.unit_id
            AND m.starts_at<=now() AND (m.ends_at IS NULL OR m.ends_at>now())) RETURNING *"""),
          {**_person_params(context), "id": entry_id, "decision": payload.decision,
           "version": expected}).mappings().first()
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "leave.decided", entry_id,
          {"decision": payload.decision})
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)
