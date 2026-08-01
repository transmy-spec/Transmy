from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import Response
from starlette.requests import Request

from app.routers.schedule import ScheduleInput, cancel_schedule, create_schedule, list_schedule
from app.security import SecurityContext, token_hash

USER = UUID("60000000-0000-4000-8000-000000000003")
TARGET = UUID("60000000-0000-4000-8000-000000000002")
ORG = UUID("10000000-0000-4000-8000-000000000001")
UNIT = UUID("40000000-0000-4000-8000-000000000001")
ENTRY = UUID("b0000000-0000-4000-8000-000000000001")


def context() -> SecurityContext:
    return SecurityContext(USER, ORG, "chefservice", "Sophie Laurent", None, token_hash("csrf"))


def request() -> Request:
    return Request({"type": "http", "headers": [
        (b"origin", b"https://localhost"), (b"x-csrf-token", b"csrf"),
    ]})


def database(connection: MagicMock, transaction: bool = False) -> MagicMock:
    value = MagicMock()
    manager = value.begin if transaction else value.connect
    manager.return_value.__enter__.return_value = connection
    return value


def mapped(rows: list[dict[str, object]]) -> MagicMock:
    value = MagicMock()
    value.mappings.return_value.__iter__.return_value = iter(rows)
    return value


def test_schedule_period_validation_and_list() -> None:
    start = datetime.now(UTC)
    with pytest.raises(ValueError):
        ScheduleInput(user_id=TARGET, unit_id=UNIT, entry_type="shift",
                      starts_at=start, ends_at=start)
    connection = MagicMock()
    connection.execute.side_effect = [mapped([{"id": ENTRY, "entry_type": "shift",
      "user_id": TARGET}]), mapped([]), mapped([]),
      mapped([{"id": TARGET, "display_name": "Alex"}]),
      mapped([{"id": USER, "display_name": "Camille Martin"}])]
    with patch("app.routers.schedule.engine", database(connection)), patch(
        "app.routers.schedule.require_permission"
    ):
        response = list_schedule(start, start + timedelta(days=7), context())
    assert response["items"][0]["id"] == ENTRY
    assert response["members"][0]["display_name"] == "Alex"
    assert response["people"][0]["display_name"] == "Camille Martin"


def test_create_and_cancel_schedule_entry() -> None:
    start = datetime.now(UTC) + timedelta(days=1)
    payload = ScheduleInput(user_id=TARGET, unit_id=UNIT, entry_type="absence",
                            starts_at=start, ends_at=start + timedelta(hours=8))
    connection = MagicMock()
    connection.execute.side_effect = [
        MagicMock(first=lambda: (1,)), MagicMock(first=lambda: None), MagicMock(), MagicMock(),
    ]
    with patch("app.routers.schedule.engine", database(connection, True)), patch(
        "app.routers.schedule.require_permission"
    ):
        response = create_schedule(payload, request(), Response(), context())
    assert response["entry_type"] == "absence"

    connection = MagicMock()
    connection.execute.side_effect = [MagicMock(first=lambda: (ENTRY,)), MagicMock()]
    with patch("app.routers.schedule.engine", database(connection, True)), patch(
        "app.routers.schedule.require_permission"
    ), patch("app.routers.schedule.permissions_for", return_value={"schedule.manage"}):
        cancel_schedule(ENTRY, request(), context(), '"1"')
    assert connection.execute.call_count == 2
