import json
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text

from app.database import engine
from app.security import (
    SecurityContext,
    get_security_context,
    permissions_for,
    require_permission,
    verify_csrf,
)

router = APIRouter(prefix="/api/v1", tags=["supported people"])


class PersonCreate(BaseModel):
    family_name: str = Field(min_length=2, max_length=120)
    given_name: str = Field(min_length=2, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None
    unit_id: UUID


class PersonUpdate(BaseModel):
    family_name: str | None = Field(default=None, min_length=2, max_length=120)
    given_name: str | None = Field(default=None, min_length=2, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None

    @model_validator(mode="after")
    def require_change(self) -> "PersonUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class ArchiveInput(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class AssignmentInput(BaseModel):
    unit_id: UUID
    starts_at: datetime | None = None
    is_primary: bool = False


class TransferInput(BaseModel):
    unit_id: UUID
    reason: str = Field(min_length=5, max_length=500)


def _etag(version: int) -> str:
    return f'"{version}"'


def _parse_if_match(value: str | None) -> int:
    if value is None:
        raise HTTPException(status.HTTP_428_PRECONDITION_REQUIRED, "precondition_required")
    try:
        return int(value.strip('"'))
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_etag") from error


def _scoped_person_query() -> str:
    return """
        SELECT DISTINCT ON (p.id)
               p.id, p.internal_reference, p.family_name, p.given_name, p.preferred_name,
               p.birth_date, p.status, p.archived_at, p.archive_reason, p.row_version,
               u.id AS unit_id, u.name AS unit_name, s.name AS service_name,
               e.name AS establishment_name
        FROM app.supported_person p
        JOIN app.person_assignment pa ON pa.person_id = p.id
          AND pa.starts_at <= now() AND (pa.ends_at IS NULL OR pa.ends_at > now())
        JOIN app.unit u ON u.id = pa.unit_id
        JOIN app.service s ON s.id = u.service_id
        JOIN app.establishment e ON e.id = s.establishment_id
        WHERE p.organization_id = :organization_id
          AND EXISTS (
            SELECT 1
            FROM app.role_assignment ra
            JOIN app.role_permission rp ON rp.role_id = ra.role_id
            WHERE ra.user_id = :user_id AND rp.permission_code = :scope_permission
              AND ra.starts_at <= now() AND (ra.ends_at IS NULL OR ra.ends_at > now())
              AND (
                (ra.scope_type = 'organization' AND ra.scope_id = e.organization_id)
                OR (ra.scope_type = 'establishment' AND ra.scope_id = e.id)
                OR (ra.scope_type = 'unit' AND ra.scope_id = u.id)
              )
          )
    """


def _person_params(
    context: SecurityContext, scope_permission: str = "person.read"
) -> dict[str, Any]:
    return {
        "organization_id": context.organization_id,
        "user_id": context.user_id,
        "scope_permission": scope_permission,
    }


def _can_use_unit(context: SecurityContext, unit_id: UUID, permission: str) -> bool:
    with engine.connect() as connection:
        return (
            connection.execute(
                text(
                    """
                    SELECT 1 FROM app.unit u
                    JOIN app.service s ON s.id = u.service_id
                    JOIN app.establishment e ON e.id = s.establishment_id
                    WHERE u.id = :unit_id AND u.status = 'active'
                      AND e.organization_id = :organization_id
                      AND EXISTS (
                        SELECT 1
                        FROM app.role_assignment ra
                        JOIN app.role_permission rp ON rp.role_id = ra.role_id
                        WHERE ra.user_id = :user_id AND rp.permission_code = :permission
                          AND ra.starts_at <= now()
                          AND (ra.ends_at IS NULL OR ra.ends_at > now())
                          AND (
                            (ra.scope_type = 'organization'
                             AND ra.scope_id = e.organization_id)
                            OR (ra.scope_type = 'establishment' AND ra.scope_id = e.id)
                            OR (ra.scope_type = 'unit' AND ra.scope_id = u.id)
                          )
                      )
                    """
                ),
                {
                    **_person_params(context),
                    "unit_id": unit_id,
                    "permission": permission,
                },
            ).first()
            is not None
        )


def _audit(
    connection: Any,
    context: SecurityContext,
    event_type: str,
    person_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO audit.event
              (organization_id, actor_user_id, event_type, target_type, target_id, metadata)
            VALUES (:organization_id, :user_id, :event_type, 'supported_person', :person_id,
                    CAST(:metadata AS jsonb))
            """
        ),
        {
            **_person_params(context),
            "event_type": event_type,
            "person_id": person_id,
            "metadata": json.dumps(metadata or {}),
        },
    )


@router.get("/people")
def list_people(
    context: Annotated[SecurityContext, Depends(get_security_context)],
    query: Annotated[str | None, Query(min_length=2, max_length=120)] = None,
    person_status: Annotated[Literal["active", "archived"], Query(alias="status")] = "active",
) -> dict[str, Any]:
    require_permission(context, "person.search")
    if person_status == "archived" and "person.archive.read" not in permissions_for(context):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access_denied")
    sql = _scoped_person_query() + " AND p.status = :status"
    params = {**_person_params(context), "status": person_status, "query": query}
    if query:
        sql += """
          AND (p.family_name ILIKE '%' || :query || '%'
               OR p.given_name ILIKE '%' || :query || '%'
               OR p.preferred_name ILIKE '%' || :query || '%'
               OR p.internal_reference ILIKE '%' || :query || '%')
        """
    sql += " ORDER BY p.id, pa.is_primary DESC, pa.starts_at DESC LIMIT 50"
    with engine.connect() as connection:
        rows = connection.execute(text(sql), params).mappings()
        return {"items": [dict(row) for row in rows], "next_cursor": None}


@router.get("/people/authorized-units")
def list_authorized_units(
    context: Annotated[SecurityContext, Depends(get_security_context)],
    permission: Annotated[Literal["person.create", "person.update"], Query()] = "person.update",
) -> dict[str, Any]:
    require_permission(context, permission)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT DISTINCT u.id, u.name, s.name AS service_name,
                       e.name AS establishment_name
                FROM app.unit u
                JOIN app.service s ON s.id = u.service_id
                JOIN app.establishment e ON e.id = s.establishment_id
                JOIN app.role_assignment ra ON ra.user_id = :user_id
                JOIN app.role_permission rp ON rp.role_id = ra.role_id
                WHERE e.organization_id = :organization_id
                  AND u.status = 'active' AND rp.permission_code = :permission
                  AND ra.starts_at <= now() AND (ra.ends_at IS NULL OR ra.ends_at > now())
                  AND (
                    (ra.scope_type = 'organization' AND ra.scope_id = e.organization_id)
                    OR (ra.scope_type = 'establishment' AND ra.scope_id = e.id)
                    OR (ra.scope_type = 'unit' AND ra.scope_id = u.id)
                  )
                ORDER BY e.name, s.name, u.name
                """
            ),
            {
                **_person_params(context),
                "permission": permission,
            },
        ).mappings()
    return {"items": [dict(row) for row in rows]}


@router.post("/people", status_code=status.HTTP_201_CREATED)
def create_person(
    payload: PersonCreate,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "person.create")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    if not _can_use_unit(context, payload.unit_id, "person.create"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    person_id = uuid4()
    assignment_id = uuid4()
    reference = f"HZN-{person_id.hex[:8].upper()}"
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO app.supported_person
                  (id, organization_id, internal_reference, family_name, given_name,
                   preferred_name, birth_date)
                VALUES (:id, :organization_id, :reference, :family_name, :given_name,
                        :preferred_name, :birth_date)
                """
            ),
            {
                "id": person_id,
                "organization_id": context.organization_id,
                "reference": reference,
                "family_name": payload.family_name.strip(),
                "given_name": payload.given_name.strip(),
                "preferred_name": (
                    payload.preferred_name.strip() if payload.preferred_name else None
                ),
                "birth_date": payload.birth_date,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO app.person_assignment
                  (id, person_id, unit_id, is_primary, created_by)
                VALUES (:id, :person_id, :unit_id, true, :user_id)
                """
            ),
            {
                "id": assignment_id,
                "person_id": person_id,
                "unit_id": payload.unit_id,
                "user_id": context.user_id,
            },
        )
        _audit(
            connection,
            context,
            "person.created",
            person_id,
            {"unit_id": str(payload.unit_id), "assignment_id": str(assignment_id)},
        )
    response.headers["ETag"] = _etag(1)
    return {"id": str(person_id), "internal_reference": reference, "row_version": 1}


@router.get("/people/{person_id}")
def get_person(
    person_id: UUID,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "person.read")
    with engine.begin() as connection:
        row = (
            connection.execute(
                text(_scoped_person_query() + " AND p.id = :person_id"),
                {**_person_params(context), "person_id": person_id},
            )
            .mappings()
            .first()
        )
        if not row or (
            row["status"] == "archived" and "person.archive.read" not in permissions_for(context)
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        _audit(connection, context, "person.viewed", person_id)
    response.headers["ETag"] = _etag(row["row_version"])
    return dict(row)


@router.patch("/people/{person_id}")
def update_person(
    person_id: UUID,
    payload: PersonUpdate,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "person.update")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected_version = _parse_if_match(if_match)
    values = payload.model_dump(exclude_unset=True)
    assignments = ", ".join(f"{field} = :{field}" for field in values)
    with engine.begin() as connection:
        scoped = connection.execute(
            text(_scoped_person_query() + " AND p.id = :person_id AND p.status = 'active'"),
            {**_person_params(context, "person.update"), "person_id": person_id},
        ).first()
        if not scoped:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        updated = (
            connection.execute(
                text(
                    f"""
                UPDATE app.supported_person SET {assignments}, updated_at = now(),
                  row_version = row_version + 1
                WHERE id = :person_id AND row_version = :expected_version
                RETURNING id, internal_reference, family_name, given_name, preferred_name,
                          birth_date, status, row_version
                """  # noqa: S608 - Column names come from the validated Pydantic model.
                ),
                {**values, "person_id": person_id, "expected_version": expected_version},
            )
            .mappings()
            .first()
        )
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "person.updated", person_id, {"fields": sorted(values)})
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)


@router.post("/people/{person_id}/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(
    person_id: UUID,
    payload: AssignmentInput,
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "person.update")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    if not _can_use_unit(context, payload.unit_id, "person.update"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    assignment_id = uuid4()
    with engine.begin() as connection:
        person = connection.execute(
            text(_scoped_person_query() + " AND p.id = :person_id AND p.status = 'active'"),
            {**_person_params(context, "person.update"), "person_id": person_id},
        ).first()
        if not person:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if payload.is_primary:
            connection.execute(
                text(
                    """
                    UPDATE app.person_assignment
                    SET is_primary = false, row_version = row_version + 1
                    WHERE person_id = :person_id AND ends_at IS NULL
                    """
                ),
                {"person_id": person_id},
            )
        connection.execute(
            text(
                """
                INSERT INTO app.person_assignment
                  (id, person_id, unit_id, starts_at, is_primary, created_by)
                VALUES (:id, :person_id, :unit_id, COALESCE(:starts_at, now()),
                        :is_primary, :user_id)
                """
            ),
            {
                "id": assignment_id,
                "person_id": person_id,
                "unit_id": payload.unit_id,
                "starts_at": payload.starts_at,
                "is_primary": payload.is_primary,
                "user_id": context.user_id,
            },
        )
        _audit(connection, context, "person.assignment_created", person_id)
    return {"id": str(assignment_id), "person_id": str(person_id)}


@router.post("/people/{person_id}/transfer")
def transfer_person(
    person_id: UUID,
    payload: TransferInput,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "person.update")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected_version = _parse_if_match(if_match)
    if not _can_use_unit(context, payload.unit_id, "person.update"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")

    with engine.begin() as connection:
        person = (
            connection.execute(
                text(_scoped_person_query() + " AND p.id = :person_id AND p.status = 'active'"),
                {**_person_params(context, "person.update"), "person_id": person_id},
            )
            .mappings()
            .first()
        )
        if not person:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        version_row = (
            connection.execute(
                text(
                    """
                    UPDATE app.supported_person
                    SET updated_at = now(), row_version = row_version + 1
                    WHERE id = :person_id AND row_version = :expected_version
                    RETURNING row_version
                    """
                ),
                {"person_id": person_id, "expected_version": expected_version},
            )
            .mappings()
            .first()
        )
        if not version_row:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")

        current_assignments = list(
            connection.execute(
                text(
                    """
                    SELECT id, unit_id, is_primary
                    FROM app.person_assignment
                    WHERE person_id = :person_id AND starts_at <= now()
                      AND (ends_at IS NULL OR ends_at > now())
                    FOR UPDATE
                    """
                ),
                {"person_id": person_id},
            ).mappings()
        )
        destination = next(
            (row for row in current_assignments if row["unit_id"] == payload.unit_id), None
        )
        if destination and len(current_assignments) == 1 and destination["is_primary"]:
            raise HTTPException(status.HTTP_409_CONFLICT, "already_assigned")

        if destination:
            connection.execute(
                text(
                    """
                    UPDATE app.person_assignment
                    SET ends_at = now(), is_primary = false, row_version = row_version + 1
                    WHERE person_id = :person_id AND id <> :destination_id
                      AND starts_at <= now() AND (ends_at IS NULL OR ends_at > now())
                    """
                ),
                {"person_id": person_id, "destination_id": destination["id"]},
            )
            connection.execute(
                text(
                    """
                    UPDATE app.person_assignment
                    SET is_primary = true, row_version = row_version + 1
                    WHERE id = :destination_id
                    """
                ),
                {"destination_id": destination["id"]},
            )
            assignment_id = destination["id"]
        else:
            connection.execute(
                text(
                    """
                    UPDATE app.person_assignment
                    SET ends_at = now(), is_primary = false, row_version = row_version + 1
                    WHERE person_id = :person_id AND starts_at <= now()
                      AND (ends_at IS NULL OR ends_at > now())
                    """
                ),
                {"person_id": person_id},
            )
            assignment_id = uuid4()
            connection.execute(
                text(
                    """
                    INSERT INTO app.person_assignment
                      (id, person_id, unit_id, is_primary, created_by)
                    VALUES (:id, :person_id, :unit_id, true, :user_id)
                    """
                ),
                {
                    "id": assignment_id,
                    "person_id": person_id,
                    "unit_id": payload.unit_id,
                    "user_id": context.user_id,
                },
            )

        _audit(
            connection,
            context,
            "person.transferred",
            person_id,
            {
                "from_unit_ids": [str(row["unit_id"]) for row in current_assignments],
                "to_unit_id": str(payload.unit_id),
                "assignment_id": str(assignment_id),
                "destination_assignment": "promoted" if destination else "created",
                "reason": payload.reason.strip(),
            },
        )
    response.headers["ETag"] = _etag(version_row["row_version"])
    return {
        "id": str(assignment_id),
        "person_id": str(person_id),
        "unit_id": str(payload.unit_id),
        "row_version": version_row["row_version"],
    }


@router.post("/people/{person_id}/archive")
def archive_person(
    person_id: UUID,
    payload: ArchiveInput,
    request: Request,
    response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    require_permission(context, "person.archive")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected_version = _parse_if_match(if_match)
    with engine.begin() as connection:
        scoped = connection.execute(
            text(_scoped_person_query() + " AND p.id = :person_id AND p.status = 'active'"),
            {**_person_params(context, "person.archive"), "person_id": person_id},
        ).first()
        if not scoped:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        archived = (
            connection.execute(
                text(
                    """
                UPDATE app.supported_person
                SET status = 'archived', archived_at = now(), archived_by = :user_id,
                    archive_reason = :reason, updated_at = now(), row_version = row_version + 1
                WHERE id = :person_id AND row_version = :expected_version
                RETURNING id, status, archived_at, row_version
                """
                ),
                {
                    "user_id": context.user_id,
                    "reason": payload.reason.strip(),
                    "person_id": person_id,
                    "expected_version": expected_version,
                },
            )
            .mappings()
            .first()
        )
        if not archived:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        _audit(connection, context, "person.archived", person_id)
    response.headers["ETag"] = _etag(archived["row_version"])
    return dict(archived)
