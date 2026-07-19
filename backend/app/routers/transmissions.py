import hashlib
import json
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.routers.people import _etag, _parse_if_match, _person_params, _scoped_person_query
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1", tags=["transmissions"])


class TransmissionCreate(BaseModel):
    person_id: UUID
    category_id: UUID
    importance_level_id: UUID
    content: str = Field(min_length=2, max_length=10000)


class DraftUpdate(BaseModel):
    category_id: UUID | None = None
    importance_level_id: UUID | None = None
    content: str | None = Field(default=None, min_length=2, max_length=10000)


class CorrectionInput(BaseModel):
    content: str = Field(min_length=2, max_length=10000)
    reason: str = Field(min_length=5, max_length=500)


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _base_query() -> str:
    return """
        SELECT t.id, t.person_id, t.unit_id, t.status, t.author_id, t.published_at,
               t.selected_for_handover, t.row_version, p.family_name, p.given_name,
               p.preferred_name, c.id AS category_id, c.label AS category_label, c.color,
               i.id AS importance_level_id, i.code AS importance_code,
               i.label AS importance_label, i.requires_acknowledgement,
               v.id AS version_id, v.version_number, v.content, v.change_reason,
               v.created_at, u.display_name AS author_name,
               (t.author_id = :user_id OR EXISTS (
                       SELECT 1 FROM app.transmission_acknowledgement a
                       WHERE a.transmission_version_id = v.id AND a.user_id = :user_id))
                 AS acknowledged
        FROM app.transmission t
        JOIN app.supported_person p ON p.id = t.person_id
        JOIN app.transmission_category c ON c.id = t.category_id
        JOIN app.importance_level i ON i.id = t.importance_level_id
        JOIN app.transmission_version v ON v.id = t.current_version_id
        JOIN app.user_account u ON u.id = t.author_id
        WHERE t.organization_id = :organization_id
          AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id = :user_id
                      AND m.unit_id = t.unit_id AND m.starts_at <= now()
                      AND (m.ends_at IS NULL OR m.ends_at > now()))
    """


def _audit(connection: Any, context: SecurityContext, event: str, target_id: UUID) -> None:
    connection.execute(
        text("""INSERT INTO audit.event
              (organization_id, actor_user_id, event_type, target_type, target_id, metadata)
            VALUES (:organization_id, :user_id, :event, 'transmission', :target_id,
                    CAST(:metadata AS jsonb))"""),
        {
            **_person_params(context),
            "event": event,
            "target_id": target_id,
            "metadata": json.dumps({}),
        },
    )


def _load(connection: Any, context: SecurityContext, transmission_id: UUID) -> Any:
    return (
        connection.execute(
            text(_base_query() + " AND t.id = :id"),
            {**_person_params(context), "id": transmission_id},
        )
        .mappings()
        .first()
    )


@router.get("/transmission-references")
def references(
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "taxonomy.read")
    with engine.connect() as connection:
        categories = connection.execute(
            text("""SELECT id, code, label, color
            FROM app.transmission_category WHERE organization_id = :organization_id
            AND status = 'active' ORDER BY sort_order"""),
            _person_params(context),
        ).mappings()
        levels = connection.execute(
            text("""SELECT id, code, label, rank,
            requires_acknowledgement FROM app.importance_level
            WHERE organization_id = :organization_id AND status = 'active' ORDER BY rank"""),
            _person_params(context),
        ).mappings()
        return {
            "categories": [dict(row) for row in categories],
            "importance_levels": [dict(row) for row in levels],
        }


@router.get("/transmissions")
def list_transmissions(
    context: Annotated[SecurityContext, Depends(get_security_context)],
    transmission_status: Literal["all", "published", "draft"] = "all",
    person_id: UUID | None = None,
) -> dict[str, Any]:
    require_permission(context, "transmission.read")
    sql = _base_query() + " AND (t.status = 'published' OR t.author_id = :user_id)"
    params: dict[str, Any] = {**_person_params(context), "person_id": person_id}
    if transmission_status != "all":
        sql += " AND t.status = :status"
        params["status"] = transmission_status
    if person_id:
        sql += " AND t.person_id = :person_id"
    sql += " ORDER BY COALESCE(t.published_at, t.updated_at) DESC, t.id LIMIT 50"
    with engine.connect() as connection:
        rows = connection.execute(text(sql), params).mappings()
        return {"items": [dict(row) for row in rows], "next_cursor": None}


@router.post("/transmissions", status_code=status.HTTP_201_CREATED)
def create_transmission(
    payload: TransmissionCreate,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "transmission.create")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    transmission_id, version_id = uuid4(), uuid4()
    with engine.begin() as connection:
        person = (
            connection.execute(
                text(_scoped_person_query() + " AND p.id = :person_id AND p.status = 'active'"),
                {**_person_params(context), "person_id": payload.person_id},
            )
            .mappings()
            .first()
        )
        reference = connection.execute(
            text("""SELECT 1 FROM app.transmission_category c
            JOIN app.importance_level i ON i.organization_id = c.organization_id
            WHERE c.id = :category_id AND i.id = :importance_id
            AND c.organization_id = :organization_id"""),
            {
                **_person_params(context),
                "category_id": payload.category_id,
                "importance_id": payload.importance_level_id,
            },
        ).first()
        if not person or not reference:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(
            text("""INSERT INTO app.transmission
            (id, organization_id, unit_id, person_id, category_id, importance_level_id, author_id)
            VALUES (:id, :organization_id, :unit_id, :person_id, :category_id,
                    :importance_id, :user_id)"""),
            {
                **_person_params(context),
                "id": transmission_id,
                "unit_id": person["unit_id"],
                "person_id": payload.person_id,
                "category_id": payload.category_id,
                "importance_id": payload.importance_level_id,
            },
        )
        content = payload.content.strip()
        connection.execute(
            text("""INSERT INTO app.transmission_version
            (id, transmission_id, version_number, content, created_by, content_hash)
            VALUES (:id, :transmission_id, 1, :content, :user_id, :content_hash)"""),
            {
                "id": version_id,
                "transmission_id": transmission_id,
                "content": content,
                "user_id": context.user_id,
                "content_hash": _hash(content),
            },
        )
        connection.execute(
            text("UPDATE app.transmission SET current_version_id = :version_id WHERE id = :id"),
            {"version_id": version_id, "id": transmission_id},
        )
        _audit(connection, context, "transmission.draft_created", transmission_id)
    response.headers["ETag"] = _etag(1)
    return {"id": str(transmission_id), "status": "draft", "row_version": 1}


@router.get("/transmissions/{transmission_id}")
def get_transmission(
    transmission_id: UUID,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "transmission.read")
    with engine.connect() as connection:
        row = _load(connection, context, transmission_id)
    if not row or (row["status"] == "draft" and row["author_id"] != context.user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    response.headers["ETag"] = _etag(row["row_version"])
    return dict(row)


@router.patch("/transmissions/{transmission_id}/draft")
def update_draft(
    transmission_id: UUID,
    payload: DraftUpdate,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "transmission.create")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        row = _load(connection, context, transmission_id)
        if not row or row["status"] != "draft" or row["author_id"] != context.user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        updated = (
            connection.execute(
                text("""UPDATE app.transmission
            SET category_id = COALESCE(:category_id, category_id),
                importance_level_id = COALESCE(:importance_id, importance_level_id),
                row_version = row_version + 1, updated_at = now()
            WHERE id = :id AND row_version = :expected RETURNING row_version"""),
                {
                    "category_id": payload.category_id,
                    "importance_id": payload.importance_level_id,
                    "id": transmission_id,
                    "expected": expected,
                },
            )
            .mappings()
            .first()
        )
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        if payload.content is not None:
            content = payload.content.strip()
            connection.execute(
                text("""UPDATE app.transmission_version
                SET content = :content, content_hash = :content_hash WHERE id = :version_id"""),
                {
                    "content": content,
                    "content_hash": _hash(content),
                    "version_id": row["version_id"],
                },
            )
        _audit(connection, context, "transmission.draft_updated", transmission_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return {"id": str(transmission_id), "status": "draft", "row_version": updated["row_version"]}


@router.post("/transmissions/{transmission_id}/publish")
def publish(
    transmission_id: UUID,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "transmission.publish")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        row = _load(connection, context, transmission_id)
        if not row or row["status"] != "draft" or row["author_id"] != context.user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        updated = (
            connection.execute(
                text("""UPDATE app.transmission SET status = 'published',
            published_at = now(), updated_at = now(), row_version = row_version + 1
            WHERE id = :id AND row_version = :expected
            RETURNING status, published_at, row_version"""),
                {"id": transmission_id, "expected": expected},
            )
            .mappings()
            .first()
        )
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "transmission.published", transmission_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)


@router.post("/transmissions/{transmission_id}/versions", status_code=status.HTTP_201_CREATED)
def correct(
    transmission_id: UUID,
    payload: CorrectionInput,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "transmission.correct")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    version_id = uuid4()
    with engine.begin() as connection:
        row = _load(connection, context, transmission_id)
        if not row or row["status"] != "published":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        number = row["version_number"] + 1
        content = payload.content.strip()
        connection.execute(
            text("""INSERT INTO app.transmission_version
            (id, transmission_id, version_number, content, change_reason, created_by,
             previous_version_id, content_hash)
            VALUES (:id, :transmission_id, :number, :content, :reason, :user_id,
                    :previous, :content_hash)"""),
            {
                "id": version_id,
                "transmission_id": transmission_id,
                "number": number,
                "content": content,
                "reason": payload.reason.strip(),
                "user_id": context.user_id,
                "previous": row["version_id"],
                "content_hash": _hash(content),
            },
        )
        updated = (
            connection.execute(
                text("""UPDATE app.transmission
            SET current_version_id = :version_id, row_version = row_version + 1,
                updated_at = now() WHERE id = :id RETURNING row_version"""),
                {"version_id": version_id, "id": transmission_id},
            )
            .mappings()
            .one()
        )
        _audit(connection, context, "transmission.corrected", transmission_id)
    response.headers["ETag"] = _etag(updated["row_version"])
    return {
        "id": str(transmission_id),
        "version_number": number,
        "row_version": updated["row_version"],
    }


@router.post(
    "/transmissions/{transmission_id}/acknowledgements", status_code=status.HTTP_201_CREATED
)
def acknowledge(
    transmission_id: UUID,
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "acknowledgement.create_self")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        row = _load(connection, context, transmission_id)
        if not row or row["status"] != "published":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if row["author_id"] == context.user_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "author_acknowledgement_not_required")
        connection.execute(
            text("""INSERT INTO app.transmission_acknowledgement
            (id, transmission_id, transmission_version_id, user_id)
            VALUES (:id, :transmission_id, :version_id, :user_id)
            ON CONFLICT (transmission_version_id, user_id) DO NOTHING"""),
            {
                "id": uuid4(),
                "transmission_id": transmission_id,
                "version_id": row["version_id"],
                "user_id": context.user_id,
            },
        )
        _audit(connection, context, "transmission.acknowledged", transmission_id)
    return {
        "transmission_id": str(transmission_id),
        "version_id": str(row["version_id"]),
        "acknowledged": True,
    }
