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
from app.security import (
    SecurityContext,
    get_security_context,
    permissions_for,
    require_permission,
    verify_csrf,
)

router = APIRouter(prefix="/api/v1/schedule", tags=["team schedule"])


class ScheduleInput(BaseModel):
    user_id: UUID
    unit_id: UUID
    entry_type: Literal["shift", "absence", "event"]
    starts_at: datetime
    ends_at: datetime
    label: str = Field(default="", max_length=120)
    participant_ids: list[UUID] = Field(default_factory=list, max_length=30)
    person_ids: list[UUID] = Field(default_factory=list, max_length=50)
    link_personalized_plans: bool = False
    recurrence_weeks: int = Field(default=0, ge=0, le=12)

    @model_validator(mode="after")
    def valid_period(self) -> "ScheduleInput":
        if self.ends_at <= self.starts_at or self.ends_at > self.starts_at + timedelta(days=7):
            raise ValueError("invalid schedule period")
        if self.entry_type == "event" and (len(self.label.strip()) < 3 or not self.participant_ids):
            raise ValueError("event requires a label and participants")
        return self


def _audit(connection: Any, context: SecurityContext, event: str, target: UUID) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id,actor_user_id,event_type,target_type,target_id,metadata)
      VALUES (:organization_id,:user_id,:event,'schedule_entry',:target,
              CAST(:metadata AS jsonb))"""),
      {**_person_params(context), "event": event, "target": target,
       "metadata": json.dumps({})})


def _entry_query() -> str:
    return """SELECT e.id,e.unit_id,e.user_id,e.entry_type,e.starts_at,e.ends_at,e.label,
      e.status,e.approval_status,e.recurrence_group_id,e.created_by,e.row_version,
      u.display_name AS user_name,un.name AS unit_name
      FROM app.schedule_entry e JOIN app.user_account u ON u.id=e.user_id
      JOIN app.unit un ON un.id=e.unit_id
      WHERE e.organization_id=:organization_id
      AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:viewer_id
        AND m.unit_id=e.unit_id AND m.starts_at<=now()
        AND (m.ends_at IS NULL OR m.ends_at>now()))"""


@router.get("")
def list_schedule(start: datetime, end: datetime,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "schedule.read")
    if end <= start or end > start + timedelta(days=31):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_period")
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(text(_entry_query() + """ AND e.status='active'
          AND e.starts_at<:end AND e.ends_at>:start ORDER BY e.starts_at,u.display_name"""),
          {"organization_id": context.organization_id, "viewer_id": context.user_id,
           "start": start, "end": end}).mappings()]
        participants = connection.execute(text("""SELECT sp.entry_id,sp.user_id,u.display_name,sp.response_status
          FROM app.schedule_participant sp JOIN app.user_account u ON u.id=sp.user_id
          JOIN app.schedule_entry e ON e.id=sp.entry_id WHERE e.organization_id=:organization_id
          AND e.status='active' AND e.starts_at<:end AND e.ends_at>:start
          ORDER BY u.display_name"""), {"organization_id": context.organization_id,
          "start": start, "end": end}).mappings()
        by_entry: dict[UUID, list[dict[str, Any]]] = {}
        for participant in participants:
            by_entry.setdefault(participant["entry_id"], []).append(dict(participant))
        people = connection.execute(text("""SELECT sp.entry_id,sp.person_id,
          concat_ws(' ',COALESCE(p.preferred_name,p.given_name),p.family_name) AS person_name
          FROM app.schedule_person sp JOIN app.supported_person p ON p.id=sp.person_id
          JOIN app.schedule_entry e ON e.id=sp.entry_id WHERE e.organization_id=:organization_id
          AND e.status='active' AND e.starts_at<:end AND e.ends_at>:start
          ORDER BY p.family_name,p.given_name"""), {"organization_id": context.organization_id,
          "start": start, "end": end}).mappings()
        people_by_entry: dict[UUID, list[dict[str, Any]]] = {}
        for person in people:
            people_by_entry.setdefault(person["entry_id"], []).append(dict(person))
        expanded: list[dict[str, Any]] = []
        for row in rows:
            invited = by_entry.get(row["id"], [])
            row["participant_names"] = [item["display_name"] for item in invited]
            row["invitation_status"] = "accepted"
            row["person_names"] = [item["person_name"] for item in people_by_entry.get(row["id"], [])]
            row["person_ids"] = [item["person_id"] for item in people_by_entry.get(row["id"], [])]
            expanded.append(row)
            for item in invited:
                if item["user_id"] != row["user_id"]:
                    expanded.append({**row, "user_id": item["user_id"], "user_name": item["display_name"],
                      "invitation_status": item["response_status"]})
        members = connection.execute(text("""SELECT DISTINCT u.id,u.display_name
          FROM app.membership viewer JOIN app.membership member ON member.unit_id=viewer.unit_id
          JOIN app.user_account u ON u.id=member.user_id
          WHERE viewer.user_id=:viewer_id AND u.organization_id=:organization_id
          AND u.status='active' AND viewer.starts_at<=now()
          AND (viewer.ends_at IS NULL OR viewer.ends_at>now())
          AND member.starts_at<=now() AND (member.ends_at IS NULL OR member.ends_at>now())
          ORDER BY u.display_name"""), {"organization_id": context.organization_id,
          "viewer_id": context.user_id}).mappings()
        supported_people = connection.execute(text("""SELECT DISTINCT p.id,
          concat_ws(' ',COALESCE(p.preferred_name,p.given_name),p.family_name) AS display_name
          FROM app.supported_person p
          JOIN app.person_assignment pa ON pa.person_id=p.id
          JOIN app.membership viewer ON viewer.unit_id=pa.unit_id
          WHERE viewer.user_id=:viewer_id AND p.organization_id=:organization_id
          AND p.status='active' AND viewer.starts_at<=now()
          AND (viewer.ends_at IS NULL OR viewer.ends_at>now())
          AND pa.starts_at<=now() AND (pa.ends_at IS NULL OR pa.ends_at>now())
          ORDER BY display_name"""), {"organization_id": context.organization_id,
          "viewer_id": context.user_id}).mappings()
        return {"items": expanded, "members": [dict(row) for row in members],
          "people": [dict(row) for row in supported_people]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleInput, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    permission = "schedule.event.create" if payload.entry_type == "event" else "schedule.manage"
    require_permission(context, permission)
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    entry_id = uuid4()
    recurrence_group_id = uuid4() if payload.entry_type == "event" and payload.recurrence_weeks else None
    if payload.entry_type == "event":
        payload.user_id = context.user_id
    with engine.begin() as connection:
        eligible = connection.execute(text("""SELECT 1 FROM app.membership manager
          JOIN app.membership member ON member.unit_id=manager.unit_id
          JOIN app.user_account u ON u.id=member.user_id
          WHERE manager.user_id=:manager AND member.user_id=:user_id
          AND manager.unit_id=:unit_id AND u.organization_id=:organization_id
          AND manager.starts_at<=now() AND (manager.ends_at IS NULL OR manager.ends_at>now())
          AND member.starts_at<=:starts AND (member.ends_at IS NULL OR member.ends_at>:starts)"""),
          {"manager": context.user_id, "user_id": payload.user_id,
           "unit_id": payload.unit_id, "organization_id": context.organization_id,
           "starts": payload.starts_at}).first()
        if not eligible:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if payload.entry_type == "event":
            requested = set(payload.participant_ids) | {context.user_id}
            eligible_count = connection.execute(text("""SELECT count(DISTINCT member.user_id)
              FROM app.membership manager JOIN app.membership member ON member.unit_id=manager.unit_id
              WHERE manager.user_id=:manager AND manager.unit_id=:unit_id
              AND member.user_id=ANY(:participants) AND manager.starts_at<=now()
              AND (manager.ends_at IS NULL OR manager.ends_at>now())
              AND member.starts_at<=now() AND (member.ends_at IS NULL OR member.ends_at>now())"""),
              {"manager": context.user_id, "unit_id": payload.unit_id,
               "participants": list(requested)}).scalar_one()
            if eligible_count != len(requested):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "participant_not_found")
            if payload.person_ids:
                people_count = connection.execute(text("""SELECT count(DISTINCT p.id)
                  FROM app.supported_person p JOIN app.person_assignment pa ON pa.person_id=p.id
                  JOIN app.membership manager ON manager.unit_id=pa.unit_id
                  WHERE manager.user_id=:manager AND pa.unit_id=:unit_id
                  AND p.organization_id=:organization_id AND p.status='active'
                  AND p.id=ANY(:people) AND manager.starts_at<=now()
                  AND (manager.ends_at IS NULL OR manager.ends_at>now())
                  AND pa.starts_at<=now() AND (pa.ends_at IS NULL OR pa.ends_at>now())"""),
                  {"manager": context.user_id, "unit_id": payload.unit_id,
                   "organization_id": context.organization_id,
                   "people": list(set(payload.person_ids))}).scalar_one()
                if people_count != len(set(payload.person_ids)):
                    raise HTTPException(status.HTTP_404_NOT_FOUND, "person_not_found")
        if payload.entry_type != "event":
            overlap = connection.execute(text("""SELECT 1 FROM app.schedule_entry
              WHERE user_id=:user_id AND status='active' AND entry_type<>'event'
              AND starts_at<:ends AND ends_at>:starts"""),
              {"user_id": payload.user_id, "starts": payload.starts_at,
               "ends": payload.ends_at}).first()
            if overlap:
                raise HTTPException(status.HTTP_409_CONFLICT, "schedule_overlap")
        connection.execute(text("""INSERT INTO app.schedule_entry
          (id,organization_id,unit_id,user_id,entry_type,starts_at,ends_at,label,created_by,recurrence_group_id)
          VALUES (:id,:organization_id,:unit_id,:target_user,:entry_type,
                  :starts,:ends,:label,:user_id,:recurrence_group_id)"""),
          {**_person_params(context), "id": entry_id, "unit_id": payload.unit_id,
           "target_user": payload.user_id, "entry_type": payload.entry_type,
           "starts": payload.starts_at, "ends": payload.ends_at,
           "label": payload.label.strip(), "recurrence_group_id": recurrence_group_id})
        if payload.entry_type == "event":
            for participant_id in set(payload.participant_ids) | {context.user_id}:
                connection.execute(text("""INSERT INTO app.schedule_participant
                  (entry_id,user_id,invited_by) VALUES (:entry,:participant,:user_id)"""),
                  {"entry": entry_id, "participant": participant_id, "user_id": context.user_id})
            for person_id in set(payload.person_ids):
                connection.execute(text("""INSERT INTO app.schedule_person
                  (entry_id,person_id,added_by) VALUES (:entry,:person,:user_id)"""),
                  {"entry": entry_id, "person": person_id, "user_id": context.user_id})
            if payload.link_personalized_plans and payload.person_ids:
                connection.execute(text("""INSERT INTO app.schedule_plan(entry_id,plan_id,linked_by)
                  SELECT :entry,p.id,:user_id FROM app.personalized_plan p
                  WHERE p.person_id=ANY(:people) AND p.organization_id=:organization_id
                  AND p.status IN ('draft','active') ON CONFLICT DO NOTHING"""),
                  {"entry": entry_id, "people": list(set(payload.person_ids)),
                   "organization_id": context.organization_id, "user_id": context.user_id})
            for week in range(1, payload.recurrence_weeks + 1):
                occurrence_id = uuid4()
                connection.execute(text("""INSERT INTO app.schedule_entry
                  (id,organization_id,unit_id,user_id,entry_type,starts_at,ends_at,label,created_by,recurrence_group_id)
                  SELECT :new_id,organization_id,unit_id,user_id,entry_type,
                  starts_at+:offset,ends_at+:offset,label,created_by,recurrence_group_id
                  FROM app.schedule_entry WHERE id=:source"""), {"new_id": occurrence_id,
                  "source": entry_id, "offset": timedelta(weeks=week)})
                connection.execute(text("""INSERT INTO app.schedule_participant(entry_id,user_id,invited_by)
                  SELECT :new_id,user_id,:user_id FROM app.schedule_participant WHERE entry_id=:source"""),
                  {"new_id": occurrence_id, "source": entry_id, "user_id": context.user_id})
                connection.execute(text("""INSERT INTO app.schedule_person(entry_id,person_id,added_by)
                  SELECT :new_id,person_id,:user_id FROM app.schedule_person WHERE entry_id=:source"""),
                  {"new_id": occurrence_id, "source": entry_id, "user_id": context.user_id})
                connection.execute(text("""INSERT INTO app.schedule_plan(entry_id,plan_id,linked_by)
                  SELECT :new_id,plan_id,:user_id FROM app.schedule_plan WHERE entry_id=:source"""),
                  {"new_id": occurrence_id, "source": entry_id, "user_id": context.user_id})
                _audit(connection, context, "schedule.recurrence_created", occurrence_id)
        _audit(connection, context, "schedule.created", entry_id)
    response.headers["ETag"] = _etag(1)
    return {"id": str(entry_id), **payload.model_dump(), "recurrence_group_id": recurrence_group_id,
      "row_version": 1, "status": "active"}


@router.post("/{entry_id}/cancel", status_code=204)
def cancel_schedule(entry_id: UUID, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> None:
    permissions = permissions_for(context)
    if "schedule.manage" not in permissions and "schedule.event.create" not in permissions:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access_denied")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        cancelled = connection.execute(text("""UPDATE app.schedule_entry e SET
          status='cancelled',updated_at=now(),row_version=row_version+1
          WHERE e.id=:id AND e.organization_id=:organization_id AND e.row_version=:version
          AND ((:can_manage AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
            AND m.unit_id=e.unit_id AND m.starts_at<=now()
            AND (m.ends_at IS NULL OR m.ends_at>now()))) OR
            (e.entry_type='event' AND e.created_by=:user_id)) RETURNING e.id"""),
          {**_person_params(context), "id": entry_id, "version": expected,
           "can_manage": "schedule.manage" in permissions}).first()
        if not cancelled:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "schedule.cancelled", entry_id)
