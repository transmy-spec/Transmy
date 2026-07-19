from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers.integrations import (
    IntegrationInput,
    _validate_endpoint,
    create_integration,
    list_integrations,
)
from app.routers.integrations import (
    test_integration as run_test,
)
from app.security import SecurityContext, token_hash

USER = UUID("60000000-0000-4000-8000-000000000001")
ORG = UUID("10000000-0000-4000-8000-000000000001")
CONNECTOR = UUID("f1000000-0000-4000-8000-000000000012")


def context() -> SecurityContext:
    return SecurityContext(USER, ORG, "admin", "Alice Bernard", None, token_hash("csrf"))


def request() -> Request:
    return Request({"type": "http", "headers": [
        (b"origin", b"https://localhost"), (b"x-csrf-token", b"csrf"),
    ]})


def database(connection: MagicMock, transaction: bool = False) -> MagicMock:
    value = MagicMock()
    manager = value.begin if transaction else value.connect
    manager.return_value.__enter__.return_value = connection
    return value


def test_endpoint_allowlist_blocks_external_and_credentials() -> None:
    assert _validate_endpoint("http://host.docker.internal:8080/events").startswith("http")
    with pytest.raises(HTTPException):
        _validate_endpoint("https://example.com/events")
    with pytest.raises(HTTPException):
        _validate_endpoint("http://user:secret@host.docker.internal/events")


def test_create_and_list_integrations() -> None:
    connection = MagicMock()
    with patch("app.routers.integrations.engine", database(connection, True)), patch(
        "app.routers.integrations.require_permission"
    ):
        created = create_integration(IntegrationInput(label="Dossier local",
          endpoint_url="http://host.docker.internal:8080/events"), request(), context())
    assert created["row_version"] == 1
    rows = MagicMock()
    rows.mappings.return_value.__iter__.return_value = iter([{"id": CONNECTOR}])
    connection.execute.return_value = rows
    with patch("app.routers.integrations.engine", database(connection)), patch(
        "app.routers.integrations.require_permission"
    ):
        listed = list_integrations(context())
    assert listed["items"][0]["id"] == CONNECTOR


def test_connector_test_sends_only_schema_metadata() -> None:
    row = MagicMock()
    row.mappings.return_value.first.return_value = {
        "endpoint_url": "http://host.docker.internal:8080/events"
    }
    connection = MagicMock()
    connection.execute.side_effect = [row, MagicMock(), MagicMock()]
    response = MagicMock(status=204)
    with patch("app.routers.integrations.engine", database(connection, True)), patch(
        "app.routers.integrations.require_permission"
    ), patch("app.routers.integrations.urlopen", return_value=response) as sender:
        result = run_test(CONNECTOR, request(), context())
    assert result["status"] == "success"
    assert result["payload_contains_business_data"] is False
    sent = sender.call_args.args[0].data.decode()
    assert "connectivity.test" in sent
    assert "person" not in sent
