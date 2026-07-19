import json
from datetime import timedelta
from typing import Annotated, Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.security import (
    SESSION_COOKIE,
    SecurityContext,
    get_security_context,
    pkce_challenge,
    random_token,
    safe_destination,
    token_hash,
    utcnow,
    verify_csrf,
)

router = APIRouter(tags=["authentication"])


@router.get("/auth/login", include_in_schema=False)
def login(next_path: Annotated[str | None, Query(alias="next")] = None) -> RedirectResponse:
    settings = get_settings()
    state = random_token()
    nonce = random_token()
    verifier = random_token(64)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM auth_session.login_attempt WHERE expires_at <= now()"))
        connection.execute(
            text(
                """
                INSERT INTO auth_session.login_attempt
                  (state_hash, nonce, code_verifier, destination, expires_at)
                VALUES (:state_hash, :nonce, :verifier, :destination, :expires_at)
                """
            ),
            {
                "state_hash": token_hash(state),
                "nonce": nonce,
                "verifier": verifier,
                "destination": safe_destination(next_path),
                "expires_at": utcnow() + timedelta(minutes=5),
            },
        )
    params = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "redirect_uri": f"{str(settings.public_url).rstrip('/')}/auth/callback",
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    return RedirectResponse(f"{settings.oidc_authorization_url}?{params}")


def _decode_id_token(id_token: str, nonce: str) -> dict[str, Any]:
    settings = get_settings()
    header = jwt.get_unverified_header(id_token)
    jwks = httpx.get(settings.oidc_jwks_url, timeout=5).json()
    key_data = next((key for key in jwks["keys"] if key["kid"] == header["kid"]), None)
    if key_data is None:
        raise jwt.InvalidTokenError("Unknown signing key")
    claims = jwt.decode(
        id_token,
        jwt.PyJWK.from_dict(key_data).key,
        algorithms=["RS256"],
        audience=settings.oidc_client_id,
        issuer=settings.oidc_issuer,
    )
    if claims.get("nonce") != nonce:
        raise jwt.InvalidTokenError("Invalid nonce")
    return claims


@router.get("/auth/callback", include_in_schema=False)
def callback(code: str, state: str) -> RedirectResponse:
    settings = get_settings()
    with engine.begin() as connection:
        attempt = (
            connection.execute(
                text(
                    """
                DELETE FROM auth_session.login_attempt
                WHERE state_hash = :state_hash AND expires_at > now()
                RETURNING nonce, code_verifier, destination
                """
                ),
                {"state_hash": token_hash(state)},
            )
            .mappings()
            .first()
        )
    if not attempt:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_login_state")
    token_response = httpx.post(
        settings.oidc_token_url,
        data={
            "grant_type": "authorization_code",
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret.get_secret_value(),
            "redirect_uri": f"{str(settings.public_url).rstrip('/')}/auth/callback",
            "code": code,
            "code_verifier": attempt["code_verifier"],
        },
        timeout=5,
    )
    if token_response.is_error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "identity_provider_rejected_login")
    try:
        claims = _decode_id_token(token_response.json()["id_token"], attempt["nonce"])
    except (KeyError, jwt.PyJWTError, httpx.HTTPError) as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_identity_token") from error
    session_token = random_token()
    csrf_token = random_token()
    with engine.begin() as connection:
        user = (
            connection.execute(
                text(
                    """
                SELECT id, organization_id, authorization_version FROM app.user_account
                WHERE issuer = :issuer AND subject = :subject AND status = 'active'
                """
                ),
                {"issuer": claims["iss"], "subject": claims["sub"]},
            )
            .mappings()
            .first()
        )
        if not user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "account_not_provisioned")
        connection.execute(
            text(
                """
                INSERT INTO auth_session.web_session
                  (id, token_hash, csrf_hash, user_id, authorization_version, expires_at)
                VALUES (:id, :token_hash, :csrf_hash, :user_id, :version, :expires_at)
                """
            ),
            {
                "id": uuid4(),
                "token_hash": token_hash(session_token),
                "csrf_hash": token_hash(csrf_token),
                "user_id": user["id"],
                "version": user["authorization_version"],
                "expires_at": utcnow() + timedelta(hours=8),
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO audit.event (organization_id, actor_user_id, event_type, metadata)
                VALUES (:organization_id, :user_id, 'session.login', CAST(:metadata AS jsonb))
                """
            ),
            {
                "organization_id": user["organization_id"],
                "user_id": user["id"],
                "metadata": json.dumps({}),
            },
        )
    response = RedirectResponse(attempt["destination"], status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=8 * 60 * 60,
    )
    response.set_cookie(
        "transmissions_csrf",
        csrf_token,
        secure=True,
        httponly=False,
        samesite="strict",
        path="/",
        max_age=8 * 60 * 60,
    )
    return response


@router.post("/api/v1/auth/logout")
def logout(
    request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    response: Response,
) -> dict[str, str]:
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    session_token = request.cookies.get(SESSION_COOKIE)
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM auth_session.web_session WHERE token_hash = :token_hash"),
            {"token_hash": token_hash(session_token or "")},
        )
        connection.execute(
            text(
                """
                INSERT INTO audit.event (organization_id, actor_user_id, event_type)
                VALUES (:organization_id, :user_id, 'session.logout')
                """
            ),
            {"organization_id": context.organization_id, "user_id": context.user_id},
        )
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True)
    response.delete_cookie("transmissions_csrf", path="/", secure=True)
    settings = get_settings()
    params = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "post_logout_redirect_uri": str(settings.public_url).rstrip("/") + "/",
        }
    )
    return {"logout_url": f"{settings.oidc_end_session_url}?{params}"}
