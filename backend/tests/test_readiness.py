from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import Response
from starlette.requests import Request

from app.routers.readiness import DecisionInput, readiness, update_decision
from app.security import SecurityContext, token_hash


def context() -> SecurityContext:
    return SecurityContext(UUID("60000000-0000-4000-8000-000000000001"),
      UUID("10000000-0000-4000-8000-000000000001"), "admin", "Alice", None,
      token_hash("csrf"))


def request() -> Request:
    return Request({"type": "http", "headers": [(b"origin", b"https://localhost"),
      (b"x-csrf-token", b"csrf")]})


def database(connection: MagicMock, transaction: bool = False) -> MagicMock:
    value = MagicMock()
    manager = value.begin if transaction else value.connect
    manager.return_value.__enter__.return_value = connection
    return value


def test_readiness_never_reports_ready_with_pending_decisions() -> None:
    decisions = MagicMock()
    decisions.mappings.return_value.__iter__.return_value = iter([
      {"code": "aipd", "status": "pending"}, {"code": "backup", "status": "validated"}])
    technical = MagicMock()
    technical.mappings.return_value.one.return_value = {
      "retention_missing": 0, "active_accounts": 3, "enabled_integrations": 0,
      "audit_events": 10, "acceptance_remaining": 0, "critical_issues": 0}
    connection = MagicMock()
    connection.execute.side_effect = [decisions, technical]
    with patch("app.routers.readiness.engine", database(connection)), patch(
      "app.routers.readiness.require_permission"):
        result = readiness(context())
    assert result["summary"]["ready"] is False
    assert result["summary"]["technical_passed"] == 6


def test_update_decision_is_versioned_and_audited() -> None:
    updated = MagicMock()
    updated.mappings.return_value.first.return_value = {
      "code": "aipd", "status": "validated", "row_version": 2}
    connection = MagicMock()
    connection.execute.side_effect = [updated, MagicMock()]
    with patch("app.routers.readiness.engine", database(connection, True)), patch(
      "app.routers.readiness.require_permission"):
        result = update_decision("aipd", DecisionInput(status="validated",
          evidence="Validation DPO du 18 juillet"), request(), Response(), context(), '"1"')
    assert result["row_version"] == 2
    assert connection.execute.call_count == 2
