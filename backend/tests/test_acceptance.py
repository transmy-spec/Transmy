from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import Response
from starlette.requests import Request

from app.routers.acceptance import AcceptanceInput, list_acceptance, update_acceptance
from app.security import SecurityContext, token_hash


def context() -> SecurityContext:
    return SecurityContext(UUID("60000000-0000-4000-8000-000000000003"),
      UUID("10000000-0000-4000-8000-000000000001"), "chef", "Sophie", None,
      token_hash("csrf"))


def request() -> Request:
    return Request({"type": "http", "headers": [(b"origin", b"https://localhost"),
      (b"x-csrf-token", b"csrf")]})


def database(connection: MagicMock, transaction: bool = False) -> MagicMock:
    value = MagicMock()
    manager = value.begin if transaction else value.connect
    manager.return_value.__enter__.return_value = connection
    return value


def test_acceptance_summary_requires_every_scenario() -> None:
    rows = MagicMock()
    rows.mappings.return_value.__iter__.return_value = iter([
      {"code": "login", "status": "passed"}, {"code": "scope", "status": "failed"}])
    connection = MagicMock()
    connection.execute.return_value = rows
    with patch("app.routers.acceptance.engine", database(connection)), patch(
      "app.routers.acceptance.require_permission"):
        result = list_acceptance(context())
    assert result["summary"] == {"passed": 1, "total": 2, "complete": False, "failed": 1}


def test_acceptance_update_is_versioned_and_audited() -> None:
    updated = MagicMock()
    updated.mappings.return_value.first.return_value = {
      "code": "login", "status": "passed", "row_version": 2}
    connection = MagicMock()
    connection.execute.side_effect = [updated, MagicMock()]
    with patch("app.routers.acceptance.engine", database(connection, True)), patch(
      "app.routers.acceptance.require_permission"):
        result = update_acceptance("login", AcceptanceInput(status="passed", notes="OK"),
          request(), Response(), context(), '"1"')
    assert result["row_version"] == 2
    assert connection.execute.call_count == 2
