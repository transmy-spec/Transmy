# ruff: noqa: E501, S608
import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
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

router = APIRouter(prefix="/api/v1", tags=["tasks and handovers"])


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    due_at: datetime
    priority: Literal["normal", "important", "urgent"] = "normal"
    person_id: UUID | None = None
    transmission_id: UUID | None = None
    assignee_user_id: UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None
    priority: Literal["normal", "important", "urgent"] | None = None
    status: Literal["todo", "in_progress"] | None = None


class AssignmentInput(BaseModel):
    user_id: UUID | None = None
    unit_id: UUID | None = None


class ReasonInput(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class HandoverCreate(BaseModel):
    period_start: datetime
    period_end: datetime


class HandoverItemInput(BaseModel):
    item_type: Literal["task", "transmission"]
    item_id: UUID
    reason: str = Field(min_length=2, max_length=500)


def _task_query() -> str:
    return """
        SELECT t.id, t.unit_id, t.person_id, t.transmission_id, t.title, t.description,
               t.status, t.due_at, t.priority, t.created_by, t.completed_at, t.row_version,
               p.family_name, p.given_name, creator.display_name AS creator_name,
               assigned.display_name AS assignee_name, tua.user_id AS assignee_user_id,
               CASE WHEN t.status NOT IN ('done','cancelled') AND t.due_at < now()
                    THEN true ELSE false END AS overdue
        FROM app.task t
        LEFT JOIN app.supported_person p ON p.id = t.person_id
        JOIN app.user_account creator ON creator.id = t.created_by
        LEFT JOIN app.task_user_assignment tua ON tua.task_id = t.id AND tua.unassigned_at IS NULL
        LEFT JOIN app.user_account assigned ON assigned.id = tua.user_id
        WHERE t.organization_id = :organization_id
          AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id = :user_id
                      AND m.unit_id = t.unit_id AND m.starts_at <= now()
                      AND (m.ends_at IS NULL OR m.ends_at > now()))
    """


def _audit(
    connection: Any, context: SecurityContext, event: str, target_type: str, target_id: UUID
) -> None:
    connection.execute(
        text("""INSERT INTO audit.event
        (organization_id, actor_user_id, event_type, target_type, target_id, metadata)
        VALUES (:organization_id, :user_id, :event, :target_type, :target_id,
                CAST(:metadata AS jsonb))"""),
        {
            **_person_params(context),
            "event": event,
            "target_type": target_type,
            "target_id": target_id,
            "metadata": json.dumps({}),
        },
    )


def _task_event(
    connection: Any,
    task_id: UUID,
    context: SecurityContext,
    event: str,
    old: str | None = None,
    new: str | None = None,
) -> None:
    connection.execute(
        text("""INSERT INTO app.task_event
        (id, task_id, event_type, actor_id, from_state, to_state)
        VALUES (:id, :task_id, :event, :user_id, :old, :new)"""),
        {
            "id": uuid4(),
            "task_id": task_id,
            "event": event,
            "user_id": context.user_id,
            "old": old,
            "new": new,
        },
    )


def _load_task(connection: Any, context: SecurityContext, task_id: UUID) -> Any:
    return (
        connection.execute(
            text(_task_query() + " AND t.id = :task_id"),
            {**_person_params(context), "task_id": task_id},
        )
        .mappings()
        .first()
    )


@router.get("/tasks")
def list_tasks(
    context: Annotated[SecurityContext, Depends(get_security_context)], task_status: str = "active"
) -> dict[str, Any]:
    require_permission(context, "task.read")
    sql = _task_query()
    if task_status == "active":
        sql += " AND t.status IN ('todo','in_progress')"
    elif task_status in {"todo", "in_progress", "done", "cancelled"}:
        sql += " AND t.status = :status"
    sql += " ORDER BY (t.due_at < now()) DESC, t.due_at, t.id LIMIT 100"
    with engine.connect() as connection:
        rows = connection.execute(
            text(sql), {**_person_params(context), "status": task_status}
        ).mappings()
        return {"items": [dict(row) for row in rows]}


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "task.create")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    if payload.assignee_user_id not in {
        None,
        context.user_id,
    } and "task.assign" not in permissions_for(context):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access_denied")
    task_id = uuid4()
    with engine.begin() as connection:
        unit = connection.execute(
            text("""SELECT m.unit_id FROM app.membership m
            WHERE m.user_id = :user_id AND m.starts_at <= now()
            AND (m.ends_at IS NULL OR m.ends_at > now()) ORDER BY m.is_primary DESC LIMIT 1"""),
            {"user_id": context.user_id},
        ).first()
        if not unit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if payload.person_id:
            visible = connection.execute(
                text("""SELECT 1 FROM app.person_assignment pa
                WHERE pa.person_id = :person_id AND pa.unit_id = :unit_id
                AND pa.ends_at IS NULL"""),
                {"person_id": payload.person_id, "unit_id": unit[0]},
            ).first()
            if not visible:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(
            text("""INSERT INTO app.task
            (id, organization_id, unit_id, person_id, transmission_id, title, description,
             due_at, priority, created_by) VALUES (:id, :organization_id, :unit_id,
             :person_id, :transmission_id, :title, :description, :due_at, :priority, :user_id)"""),
            {
                **_person_params(context),
                "id": task_id,
                "unit_id": unit[0],
                "person_id": payload.person_id,
                "transmission_id": payload.transmission_id,
                "title": payload.title.strip(),
                "description": payload.description.strip(),
                "due_at": payload.due_at,
                "priority": payload.priority,
            },
        )
        assignee = payload.assignee_user_id or context.user_id
        connection.execute(
            text("""INSERT INTO app.task_user_assignment
            (id, task_id, user_id, assigned_by) VALUES (:id, :task_id, :assignee, :user_id)"""),
            {"id": uuid4(), "task_id": task_id, "assignee": assignee, "user_id": context.user_id},
        )
        _task_event(connection, task_id, context, "task.created", None, "todo")
        _audit(connection, context, "task.created", "task", task_id)
    response.headers["ETag"] = _etag(1)
    return {"id": str(task_id), "status": "todo", "row_version": 1}


@router.get("/tasks/{task_id}")
def get_task(
    task_id: UUID,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "task.read")
    with engine.connect() as connection:
        row = _load_task(connection, context, task_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    response.headers["ETag"] = _etag(row["row_version"])
    return dict(row)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "task.update")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    values = payload.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no_change")
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    with engine.begin() as connection:
        row = _load_task(connection, context, task_id)
        if not row or row["status"] in {"done", "cancelled"}:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        updated = (
            connection.execute(
                text(f"""UPDATE app.task SET {assignments},
            updated_at = now(), row_version = row_version + 1
            WHERE id = :task_id AND row_version = :expected
            RETURNING id, status, row_version"""),
                {**values, "task_id": task_id, "expected": expected},
            )
            .mappings()
            .first()
        )
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _task_event(connection, task_id, context, "task.updated", row["status"], updated["status"])
        _audit(connection, context, "task.updated", "task", task_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)


@router.post("/tasks/{task_id}/assignments", status_code=status.HTTP_201_CREATED)
def assign_task(
    task_id: UUID,
    payload: AssignmentInput,
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "task.assign")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    if (payload.user_id is None) == (payload.unit_id is None):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "one_assignee_required")
    with engine.begin() as connection:
        row = _load_task(connection, context, task_id)
        if not row or row["status"] in {"done", "cancelled"}:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(
            text(
                "UPDATE app.task_user_assignment SET unassigned_at = now() WHERE task_id = :task_id AND unassigned_at IS NULL"
            ),
            {"task_id": task_id},
        )
        connection.execute(
            text(
                "UPDATE app.task_unit_assignment SET unassigned_at = now() WHERE task_id = :task_id AND unassigned_at IS NULL"
            ),
            {"task_id": task_id},
        )
        table, column, assignee = (
            ("task_user_assignment", "user_id", payload.user_id)
            if payload.user_id
            else ("task_unit_assignment", "unit_id", payload.unit_id)
        )
        connection.execute(
            text(
                f"INSERT INTO app.{table} (id, task_id, {column}, assigned_by) VALUES (:id, :task_id, :assignee, :user_id)"
            ),
            {"id": uuid4(), "task_id": task_id, "assignee": assignee, "user_id": context.user_id},
        )
        _task_event(connection, task_id, context, "task.assigned")
    return {"task_id": str(task_id), "assigned_to": str(assignee)}


def _finish_task(
    task_id: UUID,
    request: Request,
    response: Response,
    context: SecurityContext,
    expected: int,
    new_status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        row = _load_task(connection, context, task_id)
        if not row or row["status"] in {"done", "cancelled"}:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        updated = (
            connection.execute(
                text("""UPDATE app.task SET status = :status,
            completed_by = :user_id, completed_at = now(), cancellation_reason = :reason,
            updated_at = now(), row_version = row_version + 1
            WHERE id = :task_id AND row_version = :expected RETURNING status, row_version"""),
                {
                    "status": new_status,
                    "user_id": context.user_id,
                    "reason": reason,
                    "task_id": task_id,
                    "expected": expected,
                },
            )
            .mappings()
            .first()
        )
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _task_event(connection, task_id, context, f"task.{new_status}", row["status"], new_status)
        _audit(connection, context, f"task.{new_status}", "task", task_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: UUID,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "task.update")
    return _finish_task(task_id, request, response, context, _parse_if_match(if_match), "done")


@router.post("/tasks/{task_id}/cancel")
def cancel_task(
    task_id: UUID,
    payload: ReasonInput,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "task.cancel")
    return _finish_task(
        task_id,
        request,
        response,
        context,
        _parse_if_match(if_match),
        "cancelled",
        payload.reason.strip(),
    )


@router.get("/tasks/{task_id}/events")
def task_events(
    task_id: UUID, context: Annotated[SecurityContext, Depends(get_security_context)]
) -> dict[str, Any]:
    require_permission(context, "task.read")
    with engine.connect() as connection:
        if not _load_task(connection, context, task_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        rows = connection.execute(
            text("""SELECT e.id, e.event_type, e.occurred_at,
            e.from_state, e.to_state, u.display_name AS actor_name FROM app.task_event e
            JOIN app.user_account u ON u.id = e.actor_id WHERE e.task_id = :task_id
            ORDER BY e.occurred_at"""),
            {"task_id": task_id},
        ).mappings()
        return {"items": [dict(row) for row in rows]}


def _handover_query() -> str:
    return """
        SELECT h.id, h.unit_id, h.period_start, h.period_end, h.status, h.created_by,
               h.created_at, h.closed_at, h.row_version, u.name AS unit_name,
               creator.display_name AS creator_name
        FROM app.handover h JOIN app.unit u ON u.id = h.unit_id
        JOIN app.user_account creator ON creator.id = h.created_by
        WHERE h.organization_id = :organization_id
          AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id = :user_id
                      AND m.unit_id = h.unit_id AND m.starts_at <= now()
                      AND (m.ends_at IS NULL OR m.ends_at > now()))
    """


def _load_handover(connection: Any, context: SecurityContext, handover_id: UUID) -> Any:
    return (
        connection.execute(
            text(_handover_query() + " AND h.id = :handover_id"),
            {**_person_params(context), "handover_id": handover_id},
        )
        .mappings()
        .first()
    )


@router.get("/handovers")
def list_handovers(
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "handover.read")
    with engine.connect() as connection:
        rows = connection.execute(
            text(_handover_query() + " ORDER BY h.period_start DESC, h.id LIMIT 50"),
            _person_params(context),
        ).mappings()
        return {"items": [dict(row) for row in rows]}


@router.post("/handovers", status_code=status.HTTP_201_CREATED)
def create_handover(
    payload: HandoverCreate,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "handover.create")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    handover_id = uuid4()
    with engine.begin() as connection:
        unit = connection.execute(
            text("""SELECT unit_id FROM app.membership
            WHERE user_id = :user_id AND starts_at <= now()
            AND (ends_at IS NULL OR ends_at > now()) ORDER BY is_primary DESC LIMIT 1"""),
            {"user_id": context.user_id},
        ).first()
        if not unit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(
            text("""INSERT INTO app.handover
            (id, organization_id, unit_id, period_start, period_end, created_by)
            VALUES (:id, :organization_id, :unit_id, :period_start, :period_end, :user_id)"""),
            {
                **_person_params(context),
                "id": handover_id,
                "unit_id": unit[0],
                "period_start": payload.period_start,
                "period_end": payload.period_end,
            },
        )
        connection.execute(
            text("""INSERT INTO app.handover_task_item
            (id, handover_id, task_id, reason, added_by, sort_order)
            SELECT gen_random_uuid(), :handover_id, t.id, 'Echeance depassee', :user_id,
                   row_number() OVER (ORDER BY t.due_at)
            FROM app.task t WHERE t.unit_id = :unit_id
              AND t.status IN ('todo','in_progress') AND t.due_at < now()
            ON CONFLICT DO NOTHING"""),
            {"handover_id": handover_id, "user_id": context.user_id, "unit_id": unit[0]},
        )
        connection.execute(
            text("""INSERT INTO app.handover_transmission_item
            (id, handover_id, transmission_id, reason, added_by, sort_order)
            SELECT gen_random_uuid(), :handover_id, t.id, 'Transmission importante', :user_id,
                   row_number() OVER (ORDER BY t.published_at)
            FROM app.transmission t JOIN app.importance_level i ON i.id = t.importance_level_id
            WHERE t.unit_id = :unit_id AND t.status = 'published' AND i.rank >= 2
              AND t.published_at BETWEEN :period_start AND :period_end
            ON CONFLICT DO NOTHING"""),
            {
                "handover_id": handover_id,
                "user_id": context.user_id,
                "unit_id": unit[0],
                "period_start": payload.period_start,
                "period_end": payload.period_end,
            },
        )
        _audit(connection, context, "handover.created", "handover", handover_id)
    response.headers["ETag"] = _etag(1)
    return {"id": str(handover_id), "status": "draft", "row_version": 1}


@router.get("/handovers/{handover_id}")
def get_handover(
    handover_id: UUID,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "handover.read")
    with engine.connect() as connection:
        handover = _load_handover(connection, context, handover_id)
        if not handover:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        tasks = connection.execute(
            text("""SELECT i.id AS item_id, i.reason, i.reviewed_at,
            t.id, t.title, t.status, t.due_at, t.priority FROM app.handover_task_item i
            JOIN app.task t ON t.id = i.task_id WHERE i.handover_id = :id
            ORDER BY i.sort_order, i.added_at"""),
            {"id": handover_id},
        ).mappings()
        transmissions = connection.execute(
            text("""SELECT i.id AS item_id, i.reason,
            i.reviewed_at, t.id, v.content, c.label AS category_label,
            p.given_name, p.family_name FROM app.handover_transmission_item i
            JOIN app.transmission t ON t.id = i.transmission_id
            JOIN app.transmission_version v ON v.id = t.current_version_id
            JOIN app.transmission_category c ON c.id = t.category_id
            JOIN app.supported_person p ON p.id = t.person_id
            WHERE i.handover_id = :id ORDER BY i.sort_order, i.added_at"""),
            {"id": handover_id},
        ).mappings()
        payload = dict(handover)
        payload["tasks"] = [dict(row) for row in tasks]
        payload["transmissions"] = [dict(row) for row in transmissions]
    response.headers["ETag"] = _etag(handover["row_version"])
    return payload


@router.post("/handovers/{handover_id}/items", status_code=status.HTTP_201_CREATED)
def add_handover_item(
    handover_id: UUID,
    payload: HandoverItemInput,
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "handover.update")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    item_id = uuid4()
    with engine.begin() as connection:
        handover = _load_handover(connection, context, handover_id)
        if not handover or handover["status"] != "draft":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        table = (
            "handover_task_item" if payload.item_type == "task" else "handover_transmission_item"
        )
        column = "task_id" if payload.item_type == "task" else "transmission_id"
        connection.execute(
            text(f"""INSERT INTO app.{table}
            (id, handover_id, {column}, reason, added_by)
            VALUES (:id, :handover_id, :item_id, :reason, :user_id)"""),
            {
                "id": item_id,
                "handover_id": handover_id,
                "item_id": payload.item_id,
                "reason": payload.reason.strip(),
                "user_id": context.user_id,
            },
        )
    return {"id": str(item_id), "item_type": payload.item_type}


def _transition_handover(
    handover_id: UUID,
    request: Request,
    response: Response,
    context: SecurityContext,
    expected: int,
    from_states: set[str],
    to_state: str,
) -> dict[str, Any]:
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        handover = _load_handover(connection, context, handover_id)
        if not handover or handover["status"] not in from_states:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        updated = (
            connection.execute(
                text("""UPDATE app.handover SET status = :status,
            closed_by = CASE WHEN :status = 'closed' THEN :user_id ELSE NULL END,
            closed_at = CASE WHEN :status = 'closed' THEN now() ELSE NULL END,
            row_version = row_version + 1 WHERE id = :id AND row_version = :expected
            RETURNING status, row_version"""),
                {
                    "status": to_state,
                    "user_id": context.user_id,
                    "id": handover_id,
                    "expected": expected,
                },
            )
            .mappings()
            .first()
        )
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, f"handover.{to_state}", "handover", handover_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)


@router.post("/handovers/{handover_id}/open")
def open_handover(
    handover_id: UUID,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "handover.update")
    return _transition_handover(
        handover_id,
        request,
        response,
        context,
        _parse_if_match(if_match),
        {"draft", "closed"},
        "open",
    )


@router.post("/handovers/{handover_id}/close")
def close_handover(
    handover_id: UUID,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "handover.close")
    return _transition_handover(
        handover_id, request, response, context, _parse_if_match(if_match), {"open"}, "closed"
    )


@router.post("/handovers/{handover_id}/reopen")
def reopen_handover(
    handover_id: UUID,
    payload: ReasonInput,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "handover.reopen")
    _ = payload.reason
    return _transition_handover(
        handover_id, request, response, context, _parse_if_match(if_match), {"closed"}, "open"
    )
