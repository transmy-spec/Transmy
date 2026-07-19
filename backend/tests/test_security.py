from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.security import (
    SecurityContext,
    get_security_context,
    permissions_for,
    pkce_challenge,
    random_token,
    require_permission,
    safe_destination,
    token_hash,
    verify_csrf,
)


def _context() -> SecurityContext:
    return SecurityContext(
        user_id=UUID("60000000-0000-4000-8000-000000000001"),
        organization_id=UUID("10000000-0000-4000-8000-000000000001"),
        username="admin",
        display_name="Camille Martin",
        email="admin@transmissions.test",
        csrf_hash=token_hash("csrf-token"),
    )


def test_token_helpers_are_stable_and_destinations_are_local() -> None:
    assert token_hash("value") == token_hash("value")
    assert len(random_token()) > 32
    assert pkce_challenge("verifier")
    assert safe_destination("/structure") == "/structure"
    assert safe_destination("//example.test") == "/"
    assert safe_destination(None) == "/"


def test_missing_session_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_security_context(None)
    assert error.value.status_code == 401


def test_valid_session_builds_security_context() -> None:
    row = {
        "user_id": _context().user_id,
        "organization_id": _context().organization_id,
        "username": "admin",
        "display_name": "Camille Martin",
        "email": "admin@transmissions.test",
        "csrf_hash": token_hash("csrf-token"),
        "session_authorization_version": 1,
        "user_authorization_version": 1,
    }
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    connection = MagicMock()
    connection.execute.side_effect = [result, MagicMock()]
    database = MagicMock()
    database.begin.return_value.__enter__.return_value = connection
    with patch("app.security.engine", database):
        context = get_security_context("session-token")
    assert context.username == "admin"
    assert connection.execute.call_count == 2


def test_revoked_authorization_version_expires_session() -> None:
    result = MagicMock()
    result.mappings.return_value.first.return_value = {
        "session_authorization_version": 1,
        "user_authorization_version": 2,
    }
    database = MagicMock()
    database.begin.return_value.__enter__.return_value.execute.return_value = result
    with patch("app.security.engine", database), pytest.raises(HTTPException) as error:
        get_security_context("session-token")
    assert error.value.detail == "session_expired"


def test_permissions_and_required_permission() -> None:
    result = MagicMock()
    result.scalars.return_value = ["structure.read", "structure.manage"]
    database = MagicMock()
    database.connect.return_value.__enter__.return_value.execute.return_value = result
    with patch("app.security.engine", database):
        assert permissions_for(_context()) == {"structure.read", "structure.manage"}
        require_permission(_context(), "structure.manage")
        with pytest.raises(HTTPException):
            require_permission(_context(), "audit.read")


def test_csrf_requires_matching_origin_and_token() -> None:
    valid_request = Request({"type": "http", "headers": [(b"origin", b"https://localhost")]})
    verify_csrf(valid_request, _context(), "csrf-token")
    invalid_request = Request({"type": "http", "headers": [(b"origin", b"https://evil.test")]})
    with pytest.raises(HTTPException):
        verify_csrf(invalid_request, _context(), "csrf-token")
    with pytest.raises(HTTPException):
        verify_csrf(valid_request, _context(), "wrong-token")
