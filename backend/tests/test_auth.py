from unittest.mock import MagicMock, patch
from uuid import UUID

import jwt
import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.routers.auth import _decode_id_token, callback, login, logout
from app.security import SecurityContext, token_hash


def _result(first: object | None = None) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.first.return_value = first
    return result


def _context() -> SecurityContext:
    return SecurityContext(
        user_id=UUID("60000000-0000-4000-8000-000000000001"),
        organization_id=UUID("10000000-0000-4000-8000-000000000001"),
        username="admin",
        display_name="Camille Martin",
        email="admin@transmissions.test",
        csrf_hash=token_hash("csrf-token"),
    )


def test_login_creates_attempt_and_redirects_to_keycloak() -> None:
    database = MagicMock()
    with patch("app.routers.auth.engine", database):
        response = login("//unsafe.example")
    assert response.status_code == 307
    assert "code_challenge=" in response.headers["location"]
    assert "client_id=transmissions-web" in response.headers["location"]
    assert database.begin.return_value.__enter__.return_value.execute.call_count == 2


def test_decode_id_token_checks_key_and_nonce() -> None:
    response = MagicMock()
    response.json.return_value = {"keys": [{"kid": "key-id", "kty": "RSA"}]}
    with (
        patch("app.routers.auth.httpx.get", return_value=response),
        patch("app.routers.auth.jwt.get_unverified_header", return_value={"kid": "key-id"}),
        patch("app.routers.auth.jwt.PyJWK.from_dict") as from_dict,
        patch("app.routers.auth.jwt.decode", return_value={"nonce": "nonce", "sub": "subject"}),
    ):
        from_dict.return_value.key = "public-key"
        assert _decode_id_token("id-token", "nonce")["sub"] == "subject"


def test_decode_id_token_rejects_unknown_key() -> None:
    response = MagicMock()
    response.json.return_value = {"keys": []}
    with (
        patch("app.routers.auth.httpx.get", return_value=response),
        patch("app.routers.auth.jwt.get_unverified_header", return_value={"kid": "unknown"}),
        pytest.raises(jwt.InvalidTokenError),
    ):
        _decode_id_token("id-token", "nonce")


def test_callback_rejects_unknown_state() -> None:
    database = MagicMock()
    database.begin.return_value.__enter__.return_value.execute.return_value = _result()
    with patch("app.routers.auth.engine", database), pytest.raises(HTTPException) as error:
        callback("code", "state")
    assert error.value.detail == "invalid_login_state"


def test_callback_creates_opaque_session() -> None:
    attempt = {"nonce": "nonce", "code_verifier": "verifier", "destination": "/"}
    user = {
        "id": UUID("60000000-0000-4000-8000-000000000001"),
        "organization_id": UUID("10000000-0000-4000-8000-000000000001"),
        "authorization_version": 1,
    }
    connection = MagicMock()
    connection.execute.side_effect = [_result(attempt), _result(user), MagicMock(), MagicMock()]
    database = MagicMock()
    database.begin.return_value.__enter__.return_value = connection
    token_response = MagicMock(is_error=False)
    token_response.json.return_value = {"id_token": "id-token"}
    with (
        patch("app.routers.auth.engine", database),
        patch("app.routers.auth.httpx.post", return_value=token_response),
        patch(
            "app.routers.auth._decode_id_token",
            return_value={"iss": "issuer", "sub": "subject"},
        ),
    ):
        response = callback("code", "state")
    assert response.status_code == 303
    assert "__Host-transmissions_session" in response.headers.getlist("set-cookie")[0]


def test_callback_rejects_identity_provider_error() -> None:
    database = MagicMock()
    database.begin.return_value.__enter__.return_value.execute.return_value = _result(
        {"nonce": "nonce", "code_verifier": "verifier", "destination": "/"}
    )
    token_response = MagicMock(is_error=True)
    with (
        patch("app.routers.auth.engine", database),
        patch("app.routers.auth.httpx.post", return_value=token_response),
        pytest.raises(HTTPException) as error,
    ):
        callback("code", "state")
    assert error.value.detail == "identity_provider_rejected_login"


def test_logout_revokes_session_and_cookies() -> None:
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"origin", b"https://localhost"),
                (b"x-csrf-token", b"csrf-token"),
                (b"cookie", b"__Host-transmissions_session=session-token"),
            ],
        }
    )
    response = Response()
    database = MagicMock()
    with patch("app.routers.auth.engine", database):
        payload = logout(request, _context(), response)
    assert database.begin.return_value.__enter__.return_value.execute.call_count == 2
    assert "Max-Age=0" in response.headers.getlist("set-cookie")[0]
    assert payload["logout_url"].startswith(
        "https://localhost/oidc/realms/transmissions/protocol/openid-connect/logout?"
    )
    assert "post_logout_redirect_uri=https%3A%2F%2Flocalhost%2F" in payload["logout_url"]
