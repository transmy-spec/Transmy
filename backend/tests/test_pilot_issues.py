from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import Response
from starlette.requests import Request

from app.routers.pilot_issues import (
    IssueCreate,
    IssueUpdate,
    create_issue,
    list_issues,
    update_issue,
)
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


def test_issue_summary_counts_open_critical_issues() -> None:
    rows = MagicMock()
    rows.mappings.return_value.__iter__.return_value = iter([
      {"status": "open", "severity": "critical"},
      {"status": "resolved", "severity": "critical"},
      {"status": "in_progress", "severity": "major"}])
    connection = MagicMock()
    connection.execute.return_value = rows
    with patch("app.routers.pilot_issues.engine", database(connection)), patch(
      "app.routers.pilot_issues.require_permission"):
        result = list_issues(context())
    assert result["summary"] == {"open": 2, "critical": 1}


def test_create_issue_is_audited() -> None:
    connection = MagicMock()
    with patch("app.routers.pilot_issues.engine", database(connection, True)), patch(
      "app.routers.pilot_issues.require_permission"):
        result = create_issue(IssueCreate(title="Connexion impossible", description="Cas pilote",
          severity="major"), request(), context())
    assert result["status"] == "open"
    assert connection.execute.call_count == 2


def test_update_issue_is_versioned_and_audited() -> None:
    updated = MagicMock()
    updated.mappings.return_value.first.return_value = {
      "id": UUID("70000000-0000-4000-8000-000000000001"),
      "status": "resolved", "row_version": 2}
    connection = MagicMock()
    connection.execute.side_effect = [updated, MagicMock()]
    with patch("app.routers.pilot_issues.engine", database(connection, True)), patch(
      "app.routers.pilot_issues.require_permission"):
        result = update_issue(UUID("70000000-0000-4000-8000-000000000001"),
          IssueUpdate(status="resolved"), request(), Response(), context(), '"1"')
    assert result["row_version"] == 2
    assert connection.execute.call_count == 2
