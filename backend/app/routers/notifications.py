# ruff: noqa: S608
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.routers.people import _person_params
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotificationKeys(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=100)


def _notification_query() -> str:
    return """
      WITH available AS (
        SELECT 'task:' || t.id::text AS notification_key, 'task' AS kind,
          CASE WHEN t.due_at < now() THEN 'Tache en retard' ELSE 'Echeance proche' END AS title,
          t.title AS detail, t.due_at AS occurred_at,
          CASE WHEN t.due_at < now() OR t.priority = 'urgent' THEN 'urgent'
               WHEN t.priority = 'important' THEN 'important' ELSE 'normal' END AS severity,
          '/?view=work' AS target_url
        FROM app.task t
        WHERE t.organization_id=:organization_id AND t.status IN ('todo','in_progress')
          AND t.due_at <= now() + interval '48 hours'
          AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
            AND m.unit_id=t.unit_id AND m.starts_at<=now()
            AND (m.ends_at IS NULL OR m.ends_at>now()))
        UNION ALL
        SELECT 'transmission:' || t.id::text || ':' || v.version_number::text,
          'transmission', 'Transmission importante non lue', c.label,
          t.published_at, CASE WHEN i.code='urgent' THEN 'urgent' ELSE 'important' END,
          '/?view=transmissions'
        FROM app.transmission t
        JOIN app.transmission_version v ON v.id=t.current_version_id
        JOIN app.importance_level i ON i.id=t.importance_level_id
        JOIN app.transmission_category c ON c.id=t.category_id
        WHERE t.organization_id=:organization_id AND t.status='published'
          AND t.author_id<>:user_id
          AND (i.requires_acknowledgement OR i.rank >= 2)
          AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
            AND m.unit_id=t.unit_id AND m.starts_at<=now()
            AND (m.ends_at IS NULL OR m.ends_at>now()))
          AND NOT EXISTS (SELECT 1 FROM app.transmission_acknowledgement a
            WHERE a.transmission_version_id=v.id AND a.user_id=:user_id)
      )
      SELECT a.*, s.read_at, (s.read_at IS NOT NULL) AS is_read
      FROM available a LEFT JOIN app.notification_state s
        ON s.user_id=:user_id AND s.notification_key=a.notification_key
      WHERE s.dismissed_at IS NULL
      ORDER BY CASE a.severity WHEN 'urgent' THEN 0 WHEN 'important' THEN 1 ELSE 2 END,
        a.occurred_at, a.notification_key LIMIT 100
    """


@router.get("")
def list_notifications(
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "notification.read")
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(
            text(_notification_query()), _person_params(context)
        ).mappings()]
    return {"items": rows, "unread_count": sum(not row["is_read"] for row in rows)}


def _update_state(keys: list[str], context: SecurityContext, column: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"""INSERT INTO app.notification_state  # noqa: S608
          (user_id,notification_key,{column})
          SELECT :user_id,key,now() FROM unnest(CAST(:keys AS text[])) AS key
          ON CONFLICT (user_id,notification_key) DO UPDATE
          SET {column}=now(),updated_at=now()"""),
          {"user_id": context.user_id, "keys": keys})


@router.post("/read", status_code=204)
def mark_read(payload: NotificationKeys, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> None:
    require_permission(context, "notification.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    _update_state(payload.keys, context, "read_at")


@router.post("/dismiss", status_code=204)
def dismiss(payload: NotificationKeys, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> None:
    require_permission(context, "notification.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    _update_state(payload.keys, context, "dismissed_at")
