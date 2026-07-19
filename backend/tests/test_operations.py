from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import Response
from starlette.requests import Request

from app.routers.operations import (
    ExportInput,
    PolicyInput,
    create_download_ticket,
    create_export,
    download_export,
    get_export,
    retention_policies,
    update_retention,
)
from app.security import SecurityContext, token_hash

USER = UUID("60000000-0000-4000-8000-000000000001")
ORG = UUID("10000000-0000-4000-8000-000000000001")
EXPORT = UUID("a0000000-0000-4000-8000-000000000001")


def context() -> SecurityContext:
    return SecurityContext(USER, ORG, "admin", "Admin Local", None, token_hash("csrf"))


def request() -> Request:
    return Request(
        {"type": "http", "headers": [(b"origin", b"https://localhost"), (b"x-csrf-token", b"csrf")]}
    )


def result(row=None, rows=None):
    value = MagicMock()
    mapped = value.mappings.return_value
    mapped.first.return_value = row
    mapped.__iter__.return_value = iter(rows or ([] if row is None else [row]))
    value.first.return_value = row
    return value


def database(connection, transaction=False):
    value = MagicMock()
    manager = value.begin if transaction else value.connect
    manager.return_value.__enter__.return_value = connection
    return value


def test_retention_list_and_update_keep_purge_disabled() -> None:
    row = {
        "data_type": "audit",
        "retention_days": None,
        "legal_basis": None,
        "status": "pilot_pending",
        "purge_enabled": False,
        "row_version": 1,
    }
    connection = MagicMock()
    connection.execute.return_value = result(rows=[row])
    response = Response()
    with patch("app.routers.operations.engine", database(connection)), patch(
        "app.routers.operations.require_permission"
    ):
        assert retention_policies(response, context())["purge_engine_enabled"] is False
        assert response.headers["etag"] == '"1"'

    connection = MagicMock()
    connection.execute.side_effect = [
        result({**row, "retention_days": 365, "row_version": 2}),
        MagicMock(),
    ]
    with patch("app.routers.operations.engine", database(connection, True)), patch(
        "app.routers.operations.require_permission"
    ):
        updated = update_retention(
            "audit", PolicyInput(retention_days=365), request(), Response(), context(), '"1"'
        )
    assert updated["purge_enabled"] is False


def test_export_creation_status_and_ticket() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [
        result(rows=[{"unit": "Unite A", "active_people": 1}]),
        MagicMock(),
        MagicMock(),
    ]
    with patch("app.routers.operations.engine", database(connection, True)), patch(
        "app.routers.operations.require_permission"
    ):
        created = create_export(
            ExportInput(export_type="activity_summary", reason="Pilotage mensuel"),
            request(),
            context(),
        )
    assert created["status"] == "ready"
    assert created["record_count"] == 1

    export_row = {
        "id": EXPORT,
        "export_type": "activity_summary",
        "format": "json",
        "status": "ready",
        "record_count": 1,
        "sha256": "abc",
        "created_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC),
        "downloaded_at": None,
    }
    connection = MagicMock()
    connection.execute.return_value = result(export_row)
    with patch("app.routers.operations.engine", database(connection)), patch(
        "app.routers.operations.require_permission"
    ):
        assert get_export(EXPORT, context())["id"] == EXPORT

    connection = MagicMock()
    connection.execute.side_effect = [result((EXPORT,)), MagicMock()]
    with patch("app.routers.operations.engine", database(connection, True)), patch(
        "app.routers.operations.require_permission"
    ), patch("app.routers.operations.random_token", return_value="one-time-token"):
        ticket = create_download_ticket(EXPORT, request(), context())
    assert ticket["download_url"].endswith("one-time-token")


def test_json_export_download_is_single_use_and_not_cached() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [
        result({"id": EXPORT, "format": "json", "result_payload": [{"unit": "Unite A"}]}),
        MagicMock(),
        MagicMock(),
    ]
    with patch("app.routers.operations.engine", database(connection, True)), patch(
        "app.routers.operations.require_permission"
    ):
        response = download_export("one-time-token", context())
    assert response.headers["cache-control"] == "no-store"
    assert response.status_code == 200
