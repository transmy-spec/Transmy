# ruff: noqa: E501
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import Response
from starlette.requests import Request

from app.routers.advanced_schedule import (
    EventUpdate,
    InvitationResponse,
    LeaveDecision,
    LeaveRequest,
    decide_leave,
    request_leave,
    respond_invitation,
    update_event,
)
from app.security import SecurityContext, token_hash

USER = UUID("60000000-0000-4000-8000-000000000003")
ORG = UUID("10000000-0000-4000-8000-000000000001")
UNIT = UUID("40000000-0000-4000-8000-000000000001")
ENTRY = UUID("b1000000-0000-4000-8000-000000000001")


def context() -> SecurityContext:
    return SecurityContext(USER, ORG, "chef", "Sophie", None, token_hash("csrf"))


def request() -> Request:
    return Request({"type": "http", "headers": [(b"origin", b"https://localhost"),
      (b"x-csrf-token", b"csrf")]})


def database(connection: MagicMock) -> MagicMock:
    value = MagicMock()
    value.begin.return_value.__enter__.return_value = connection
    return value


def test_invitation_response_and_event_update() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [MagicMock(first=lambda: ("accepted",)), MagicMock()]
    with patch("app.routers.advanced_schedule.engine", database(connection)), patch(
      "app.routers.advanced_schedule.require_permission"):
        result = respond_invitation(ENTRY, InvitationResponse(response="accepted"), request(), context())
    assert result["response_status"] == "accepted"

    start = datetime.now(UTC) + timedelta(days=1)
    updated = MagicMock()
    updated.mappings.return_value.first.return_value = {"id": ENTRY, "row_version": 2}
    connection = MagicMock()
    connection.execute.side_effect = [MagicMock(first=lambda: None), updated, MagicMock()]
    with patch("app.routers.advanced_schedule.engine", database(connection)), patch(
      "app.routers.advanced_schedule.require_permission"):
        result = update_event(ENTRY, EventUpdate(label="Reunion equipe", starts_at=start,
          ends_at=start + timedelta(hours=1)), request(), Response(), context(), '"1"')
    assert result["row_version"] == 2


def test_leave_request_and_decision() -> None:
    start = datetime.now(UTC) + timedelta(days=2)
    connection = MagicMock()
    connection.execute.side_effect = [MagicMock(first=lambda: (1,)),
      MagicMock(first=lambda: None), MagicMock(), MagicMock()]
    with patch("app.routers.advanced_schedule.engine", database(connection)), patch(
      "app.routers.advanced_schedule.require_permission"):
        result = request_leave(LeaveRequest(unit_id=UNIT, starts_at=start,
          ends_at=start + timedelta(days=1), leave_type="paid_leave"), request(), context())
    assert result["approval_status"] == "pending"

    updated = MagicMock()
    updated.mappings.return_value.first.return_value = {"id": ENTRY,
      "approval_status": "approved", "row_version": 2}
    connection = MagicMock()
    connection.execute.side_effect = [updated, MagicMock()]
    with patch("app.routers.advanced_schedule.engine", database(connection)), patch(
      "app.routers.advanced_schedule.require_permission"):
        result = decide_leave(ENTRY, LeaveDecision(decision="approved"), request(),
          Response(), context(), '"1"')
    assert result["approval_status"] == "approved"
