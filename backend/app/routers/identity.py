import json
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import get_settings
from app.database import engine
from app.keycloak_admin import (
    KeycloakProvisioningError,
    KeycloakUserConflictError,
    create_user,
    delete_user,
)
from app.security import (
    SecurityContext,
    get_security_context,
    permissions_for,
    random_token,
    require_permission,
    token_hash,
    verify_csrf,
)

router = APIRouter(prefix="/api/v1", tags=["identity and authorization"])


class NameInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class UserStatusInput(BaseModel):
    status: str
    reason: str = Field(min_length=5, max_length=500)


class MembershipInput(BaseModel):
    unit_id: UUID
    is_primary: bool = False


class ReasonInput(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class UserInvitationInput(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9._-]+$")
    display_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role_code: str
    unit_id: UUID


def _invitation_url(token: str) -> str:
    return f"{str(get_settings().public_url).rstrip('/')}/#activation={token}"


def _create_invitation_ticket(connection: Any, user_id: UUID) -> tuple[str, datetime]:
    token = random_token(48)
    expires_at = datetime.now(UTC) + timedelta(hours=48)
    connection.execute(
        text(
            """
            UPDATE auth_session.account_activation SET revoked_at=now()
            WHERE user_id=:user_id AND consumed_at IS NULL AND revoked_at IS NULL;
            INSERT INTO auth_session.account_activation
              (id,user_id,token_hash,purpose,expires_at)
            VALUES (:id,:user_id,:token_hash,'user_invitation',:expires_at)
            """
        ),
        {
            "id": uuid4(),
            "user_id": user_id,
            "token_hash": token_hash(token),
            "expires_at": expires_at,
        },
    )
    return token, expires_at


def _audit_user(connection: Any, context: SecurityContext, event: str, user_id: UUID,
    metadata: dict[str, Any]) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id,actor_user_id,event_type,target_type,target_id,metadata)
      VALUES (:organization_id,:actor,:event,'user',:target,CAST(:metadata AS jsonb))"""),
      {"organization_id": context.organization_id, "actor": context.user_id, "event": event,
       "target": user_id, "metadata": json.dumps(metadata)})


def _roles(context: SecurityContext) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                text(
                    """
                    SELECT r.code, r.label, ra.scope_type, ra.scope_id
                    FROM app.role_assignment ra
                    JOIN app.role r ON r.id = ra.role_id
                    WHERE ra.user_id = :user_id AND ra.starts_at <= now()
                      AND (ra.ends_at IS NULL OR ra.ends_at > now())
                    ORDER BY r.label
                    """
                ),
                {"user_id": context.user_id},
            ).mappings()
        ]


def _contexts(context: SecurityContext) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT u.id, u.name, s.name AS service_name, e.name AS establishment_name
                FROM app.membership m
                JOIN app.unit u ON u.id = m.unit_id
                JOIN app.service s ON s.id = u.service_id
                JOIN app.establishment e ON e.id = s.establishment_id
                WHERE m.user_id = :user_id AND m.starts_at <= now()
                  AND (m.ends_at IS NULL OR m.ends_at > now()) AND u.status = 'active'
                ORDER BY m.is_primary DESC, e.name, s.name, u.name
                """
            ),
            {"user_id": context.user_id},
        ).mappings()
        return [dict(row) for row in rows]


@router.get("/session")
def session(
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    csrf_token = request.cookies.get("transmissions_csrf", "")
    return {
        "user": {
            "id": str(context.user_id),
            "username": context.username,
            "display_name": context.display_name,
            "email": context.email,
        },
        "roles": _roles(context),
        "permissions": sorted(permissions_for(context)),
        "contexts": _contexts(context),
        "csrf_token": csrf_token,
    }


@router.get("/structure")
def structure(
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "structure.read")
    with engine.connect() as connection:
        organization = (
            connection.execute(
                text("SELECT id, name, status FROM app.organization WHERE id = :id"),
                {"id": context.organization_id},
            )
            .mappings()
            .one()
        )
        rows = connection.execute(
            text(
                """
                SELECT e.id AS establishment_id, e.name AS establishment_name,
                       s.id AS service_id, s.name AS service_name,
                       u.id AS unit_id, u.name AS unit_name, u.status AS unit_status
                FROM app.establishment e
                LEFT JOIN app.service s ON s.establishment_id = e.id
                LEFT JOIN app.unit u ON u.service_id = s.id
                WHERE e.organization_id = :organization_id
                ORDER BY e.name, s.name, u.name
                """
            ),
            {"organization_id": context.organization_id},
        ).mappings()
        return {"organization": dict(organization), "items": [dict(row) for row in rows]}


@router.get("/users")
def users(
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "user.read_minimal")
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT u.id, u.username, u.display_name, u.email, u.status,
                       COALESCE(string_agg(DISTINCT r.label, ', '), '') AS roles,
                       COALESCE(string_agg(DISTINCT un.name, ', '), '') AS units
                FROM app.user_account u
                LEFT JOIN app.role_assignment ra ON ra.user_id = u.id
                  AND ra.starts_at <= now() AND (ra.ends_at IS NULL OR ra.ends_at > now())
                LEFT JOIN app.role r ON r.id = ra.role_id
                LEFT JOIN app.membership m ON m.user_id = u.id
                  AND m.starts_at <= now() AND (m.ends_at IS NULL OR m.ends_at > now())
                LEFT JOIN app.unit un ON un.id = m.unit_id
                WHERE u.organization_id = :organization_id
                GROUP BY u.id ORDER BY u.display_name
                """
            ),
            {"organization_id": context.organization_id},
        ).mappings()
        return {"items": [dict(row) for row in rows]}


@router.post("/users/invitations", status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: UserInvitationInput,
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "role.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    if payload.role_code not in {"professional", "team_manager", "service_manager"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_role")
    with engine.connect() as connection:
        scope = connection.execute(
            text(
                """
                SELECT u.id AS unit_id,r.id AS role_id
                FROM app.unit u
                JOIN app.service s ON s.id=u.service_id
                JOIN app.establishment e ON e.id=s.establishment_id
                CROSS JOIN app.role r
                WHERE u.id=:unit_id AND e.organization_id=:organization_id
                  AND r.code=:role_code
                """
            ),
            {
                "unit_id": payload.unit_id,
                "organization_id": context.organization_id,
                "role_code": payload.role_code,
            },
        ).mappings().first()
    if not scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unit_or_role_not_found")
    try:
        keycloak_id = create_user(payload.username, payload.email, payload.display_name)
    except KeycloakUserConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "username_or_email_exists") from error
    except KeycloakProvisioningError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "identity_provider_unavailable"
        ) from error
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO app.user_account
                      (id,organization_id,issuer,subject,username,display_name,email,status)
                    VALUES (:id,:organization_id,:issuer,:subject,:username,:display_name,
                      :email,'invited');
                    INSERT INTO app.membership (id,user_id,unit_id,is_primary)
                    VALUES (:membership_id,:id,:unit_id,true);
                    INSERT INTO app.role_assignment
                      (id,user_id,role_id,scope_type,scope_id)
                    VALUES (:assignment_id,:id,:role_id,'unit',:unit_id)
                    """
                ),
                {
                    "id": keycloak_id,
                    "organization_id": context.organization_id,
                    "issuer": get_settings().oidc_issuer,
                    "subject": str(keycloak_id),
                    "username": payload.username,
                    "display_name": payload.display_name.strip(),
                    "email": payload.email.lower(),
                    "membership_id": uuid4(),
                    "assignment_id": uuid4(),
                    "unit_id": payload.unit_id,
                    "role_id": scope["role_id"],
                },
            )
            token, expires_at = _create_invitation_ticket(connection, keycloak_id)
            _audit_user(
                connection,
                context,
                "user.invited",
                keycloak_id,
                {"role_code": payload.role_code, "unit_id": str(payload.unit_id)},
            )
    except SQLAlchemyError as error:
        with suppress(KeycloakProvisioningError):
            delete_user(keycloak_id)
        if isinstance(error, IntegrityError):
            raise HTTPException(status.HTTP_409_CONFLICT, "username_or_email_exists") from error
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "provisioning_failed") from error
    return {
        "id": str(keycloak_id),
        "activation_url": _invitation_url(token),
        "expires_at": expires_at.isoformat(),
    }


@router.post("/users/{user_id}/invitation")
def renew_user_invitation(
    user_id: UUID,
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, str]:
    require_permission(context, "role.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        user = connection.execute(
            text(
                "SELECT id FROM app.user_account WHERE id=:id "
                "AND organization_id=:organization_id AND status='invited' FOR UPDATE"
            ),
            {"id": user_id, "organization_id": context.organization_id},
        ).first()
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "invited_user_not_found")
        token, expires_at = _create_invitation_ticket(connection, user_id)
        _audit_user(connection, context, "user.invitation_renewed", user_id, {})
    return {"activation_url": _invitation_url(token), "expires_at": expires_at.isoformat()}


@router.post("/users/{user_id}/invitation/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_user_invitation(
    user_id: UUID,
    payload: ReasonInput,
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> None:
    require_permission(context, "role.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        revoked = connection.execute(
            text(
                """
                UPDATE auth_session.account_activation a SET revoked_at=now()
                FROM app.user_account u
                WHERE a.user_id=:user_id AND u.id=a.user_id
                  AND u.organization_id=:organization_id AND u.status='invited'
                  AND a.consumed_at IS NULL AND a.revoked_at IS NULL
                RETURNING a.id
                """
            ),
            {"user_id": user_id, "organization_id": context.organization_id},
        ).first()
        if not revoked:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "active_invitation_not_found")
        _audit_user(
            connection, context, "user.invitation_revoked", user_id,
            {"reason": payload.reason.strip()},
        )


@router.get("/users/{user_id}")
def user_detail(user_id: UUID,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "user.read_minimal")
    with engine.connect() as connection:
        user = connection.execute(text("""SELECT id,username,display_name,email,status
          FROM app.user_account WHERE id=:id AND organization_id=:organization_id"""),
          {"id": user_id, "organization_id": context.organization_id}).mappings().first()
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        memberships = connection.execute(text("""SELECT m.id,m.unit_id,u.name AS unit_name,
          s.name AS service_name,m.is_primary,m.starts_at,m.ends_at
          FROM app.membership m JOIN app.unit u ON u.id=m.unit_id
          JOIN app.service s ON s.id=u.service_id WHERE m.user_id=:id
          ORDER BY (m.ends_at IS NULL) DESC,m.is_primary DESC,m.starts_at DESC"""),
          {"id": user_id}).mappings()
    return {**dict(user), "memberships": [dict(row) for row in memberships]}


@router.patch("/users/{user_id}/status")
def update_user_status(user_id: UUID, payload: UserStatusInput, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "role.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    if payload.status not in {"active", "disabled"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_status")
    if user_id == context.user_id and payload.status == "disabled":
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot_disable_self")
    with engine.begin() as connection:
        updated = connection.execute(text("""UPDATE app.user_account
          SET status=:status,authorization_version=authorization_version+1
          WHERE id=:id AND organization_id=:organization_id AND status<>'invited'
          RETURNING id,status"""),
          {"status": payload.status, "id": user_id,
           "organization_id": context.organization_id}).mappings().first()
        if not updated:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(text("DELETE FROM auth_session.web_session WHERE user_id=:id"),
                           {"id": user_id})
        _audit_user(connection, context, f"user.{payload.status}", user_id,
                    {"reason": payload.reason.strip()})
    return dict(updated)


@router.post("/users/{user_id}/memberships", status_code=status.HTTP_201_CREATED)
def add_membership(user_id: UUID, payload: MembershipInput, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "membership.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    membership_id = uuid4()
    with engine.begin() as connection:
        valid = connection.execute(text("""SELECT 1 FROM app.user_account a,app.unit u
          JOIN app.service s ON s.id=u.service_id
          JOIN app.establishment e ON e.id=s.establishment_id
          WHERE a.id=:user_id AND a.organization_id=:organization_id AND u.id=:unit_id
          AND e.organization_id=:organization_id"""),
          {"user_id": user_id, "unit_id": payload.unit_id,
           "organization_id": context.organization_id}).first()
        if not valid:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if payload.is_primary:
            connection.execute(text("""UPDATE app.membership SET is_primary=false
              WHERE user_id=:user_id AND ends_at IS NULL"""), {"user_id": user_id})
        connection.execute(text("""INSERT INTO app.membership (id,user_id,unit_id,is_primary)
          VALUES (:id,:user_id,:unit_id,:primary)"""),
          {"id": membership_id, "user_id": user_id, "unit_id": payload.unit_id,
           "primary": payload.is_primary})
        connection.execute(text("""UPDATE app.user_account SET authorization_version=
          authorization_version+1 WHERE id=:user_id"""), {"user_id": user_id})
        connection.execute(text("DELETE FROM auth_session.web_session WHERE user_id=:user_id"),
                           {"user_id": user_id})
        _audit_user(connection, context, "membership.created", user_id,
                    {"unit_id": str(payload.unit_id)})
    return {"id": str(membership_id), "unit_id": str(payload.unit_id),
            "is_primary": payload.is_primary}


@router.post("/users/{user_id}/memberships/{membership_id}/revoke", status_code=204)
def revoke_membership(user_id: UUID, membership_id: UUID, payload: ReasonInput, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> None:
    require_permission(context, "membership.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        revoked = connection.execute(text("""UPDATE app.membership m
          SET ends_at=now(),is_primary=false
          FROM app.user_account a WHERE m.id=:membership_id AND m.user_id=:user_id
          AND m.ends_at IS NULL AND a.id=m.user_id AND a.organization_id=:organization_id
          RETURNING m.id"""), {"membership_id": membership_id, "user_id": user_id,
          "organization_id": context.organization_id}).first()
        if not revoked:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(text("""UPDATE app.user_account SET authorization_version=
          authorization_version+1 WHERE id=:user_id"""), {"user_id": user_id})
        connection.execute(text("DELETE FROM auth_session.web_session WHERE user_id=:user_id"),
                           {"user_id": user_id})
        _audit_user(connection, context, "membership.revoked", user_id,
                    {"membership_id": str(membership_id), "reason": payload.reason.strip()})


@router.post("/services/{service_id}/units", status_code=status.HTTP_201_CREATED)
def create_unit(
    service_id: UUID,
    payload: NameInput,
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "structure.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    unit_id = uuid4()
    with engine.begin() as connection:
        service = connection.execute(
            text(
                """
                SELECT s.id FROM app.service s
                JOIN app.establishment e ON e.id = s.establishment_id
                WHERE s.id = :service_id AND e.organization_id = :organization_id
                """
            ),
            {"service_id": service_id, "organization_id": context.organization_id},
        ).first()
        if not service:
            from fastapi import HTTPException

            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(
            text("INSERT INTO app.unit (id, service_id, name) VALUES (:id, :service_id, :name)"),
            {"id": unit_id, "service_id": service_id, "name": payload.name.strip()},
        )
        connection.execute(
            text(
                """
                INSERT INTO audit.event
                  (organization_id, actor_user_id, event_type, target_type, target_id, metadata)
                VALUES (:organization_id, :user_id, 'structure.unit_created', 'unit', :unit_id,
                        CAST(:metadata AS jsonb))
                """
            ),
            {
                "organization_id": context.organization_id,
                "user_id": context.user_id,
                "unit_id": unit_id,
                "metadata": json.dumps({"name": payload.name.strip()}),
            },
        )
    return {"id": str(unit_id), "name": payload.name.strip(), "status": "active"}


@router.get("/audit-events")
def audit_events(
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "audit.read")
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT a.id, a.event_type, a.target_type, a.target_id, a.occurred_at,
                       u.display_name AS actor_name
                FROM audit.event a
                LEFT JOIN app.user_account u ON u.id = a.actor_user_id
                WHERE a.organization_id = :organization_id
                ORDER BY a.occurred_at DESC LIMIT 50
                """
            ),
            {"organization_id": context.organization_id},
        ).mappings()
        return {"items": [dict(row) for row in rows]}
