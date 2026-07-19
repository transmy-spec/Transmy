import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Header, HTTPException, Request, status
from sqlalchemy import text

from app.config import get_settings
from app.database import engine

SESSION_COOKIE = "__Host-transmissions_session"


@dataclass(frozen=True)
class SecurityContext:
    user_id: UUID
    organization_id: UUID
    username: str
    display_name: str
    email: str | None
    csrf_hash: str


def random_token(size: int = 32) -> str:
    return secrets.token_urlsafe(size)


def token_hash(value: str) -> str:
    secret = get_settings().session_secret.get_secret_value().encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def safe_destination(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


def get_security_context(
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> SecurityContext:
    if not session_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication_required")
    with engine.begin() as connection:
        row = (
            connection.execute(
                text(
                    """
                SELECT s.user_id, u.organization_id, u.username, u.display_name, u.email,
                       s.csrf_hash, s.authorization_version AS session_authorization_version,
                       u.authorization_version AS user_authorization_version
                FROM auth_session.web_session s
                JOIN app.user_account u ON u.id = s.user_id
                WHERE s.token_hash = :token_hash AND s.expires_at > now() AND u.status = 'active'
                """
                ),
                {"token_hash": token_hash(session_token)},
            )
            .mappings()
            .first()
        )
        if not row or row["session_authorization_version"] != row["user_authorization_version"]:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session_expired")
        connection.execute(
            text(
                "UPDATE auth_session.web_session SET last_seen_at = now() "
                "WHERE token_hash = :token_hash"
            ),
            {"token_hash": token_hash(session_token)},
        )
    return SecurityContext(
        user_id=row["user_id"],
        organization_id=row["organization_id"],
        username=row["username"],
        display_name=row["display_name"],
        email=row["email"],
        csrf_hash=row["csrf_hash"],
    )


def permissions_for(context: SecurityContext) -> set[str]:
    with engine.connect() as connection:
        return set(
            connection.execute(
                text(
                    """
                    SELECT DISTINCT rp.permission_code
                    FROM app.role_assignment ra
                    JOIN app.role_permission rp ON rp.role_id = ra.role_id
                    WHERE ra.user_id = :user_id AND ra.starts_at <= now()
                      AND (ra.ends_at IS NULL OR ra.ends_at > now())
                    """
                ),
                {"user_id": context.user_id},
            ).scalars()
        )


def require_permission(context: SecurityContext, permission: str) -> None:
    if permission not in permissions_for(context):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "access_denied")


def verify_csrf(
    request: Request,
    context: SecurityContext,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    settings = get_settings()
    if request.headers.get("origin") != str(settings.public_url).rstrip("/"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid_origin")
    if not csrf_token or not hmac.compare_digest(token_hash(csrf_token), context.csrf_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid_csrf_token")


def utcnow() -> datetime:
    return datetime.now(UTC)
