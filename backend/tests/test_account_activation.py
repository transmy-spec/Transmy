from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.admin_activation import issue
from app.keycloak_admin import (
    KeycloakProvisioningError,
    KeycloakUserConflictError,
    create_user,
    delete_user,
    reset_user_password,
)
from app.routers.account_activation import (
    ActivationTokenInput,
    CompleteActivationInput,
    complete_activation,
    inspect_activation,
)

USER_ID = UUID("60000000-0000-4000-8000-000000000001")
ORG_ID = UUID("10000000-0000-4000-8000-000000000001")


def _engine_with_rows(*rows: object) -> MagicMock:
    connection = MagicMock()
    results = []
    for row in rows:
        result = MagicMock()
        result.mappings.return_value.first.return_value = row
        result.mappings.return_value.one.return_value = row
        results.append(result)
    connection.execute.side_effect = results
    context = MagicMock()
    context.__enter__.return_value = connection
    engine = MagicMock()
    engine.connect.return_value = context
    engine.begin.return_value = context
    return engine


def _ticket() -> dict[str, object]:
    return {
        "id": USER_ID,
        "user_id": USER_ID,
        "purpose": "admin_bootstrap",
        "expires_at": datetime(2026, 7, 25, 12, tzinfo=UTC),
        "username": "admin",
        "display_name": "Administrateur",
        "subject": "11111111-1111-4111-8111-111111111111",
    }


def test_inspect_activation_and_reject_unknown_ticket() -> None:
    with patch("app.routers.account_activation.engine", _engine_with_rows(_ticket())):
        result = inspect_activation(ActivationTokenInput(token=SecretStr("ticket")))
    assert result.username == "admin"
    with (
        patch("app.routers.account_activation.engine", _engine_with_rows(None)),
        pytest.raises(HTTPException) as error,
    ):
        inspect_activation(ActivationTokenInput(token=SecretStr("missing")))
    assert error.value.status_code == 404


def test_complete_activation_resets_password_and_consumes_ticket() -> None:
    payload = CompleteActivationInput(
        token=SecretStr("ticket"), password=SecretStr("A-long-local-password!")
    )
    with (
        patch("app.routers.account_activation.engine", _engine_with_rows(_ticket(), None)),
        patch("app.routers.account_activation.reset_user_password") as reset,
    ):
        complete_activation(payload)
    reset.assert_called_once_with(
        UUID("11111111-1111-4111-8111-111111111111"),
        "A-long-local-password!",
    )


def test_complete_activation_reports_keycloak_failure() -> None:
    payload = CompleteActivationInput(
        token=SecretStr("ticket"), password=SecretStr("A-long-local-password!")
    )
    with (
        patch("app.routers.account_activation.engine", _engine_with_rows(_ticket())),
        patch(
            "app.routers.account_activation.reset_user_password",
            side_effect=KeycloakProvisioningError,
        ),
        pytest.raises(HTTPException) as error,
    ):
        complete_activation(payload)
    assert error.value.status_code == 503


def test_keycloak_password_reset_uses_service_account() -> None:
    token_response = MagicMock()
    token_response.json.return_value = {"access_token": "access"}
    reset_response = MagicMock()
    with (
        patch("app.keycloak_admin.httpx.post", return_value=token_response),
        patch("app.keycloak_admin.httpx.put", return_value=reset_response) as put,
    ):
        reset_user_password(USER_ID, "A-long-local-password!")
    put.assert_called_once()
    assert put.call_args.kwargs["json"]["temporary"] is False


def test_keycloak_password_reset_hides_provider_errors() -> None:
    with (
        patch("app.keycloak_admin.httpx.post", side_effect=httpx.ConnectError("offline")),
        pytest.raises(KeycloakProvisioningError),
    ):
        reset_user_password(USER_ID, "A-long-local-password!")


def test_keycloak_user_creation_deletion_and_conflict() -> None:
    token_response = MagicMock()
    token_response.json.return_value = {"access_token": "access"}
    created = MagicMock(status_code=201)
    created.headers = {"Location": f"http://keycloak/users/{USER_ID}"}
    deleted = MagicMock()
    with (
        patch(
            "app.keycloak_admin.httpx.post",
            side_effect=[token_response, created, token_response],
        ),
        patch("app.keycloak_admin.httpx.delete", return_value=deleted) as delete,
    ):
        assert create_user("lea", "lea@example.test", "Lea Martin") == USER_ID
        delete_user(USER_ID)
    delete.assert_called_once()

    conflict = MagicMock(status_code=409)
    with (
        patch("app.keycloak_admin.httpx.post", side_effect=[token_response, conflict]),
        pytest.raises(KeycloakUserConflictError),
    ):
        create_user("lea", "lea@example.test", "Lea Martin")


def test_issue_revokes_previous_links_and_returns_fragment_url() -> None:
    engine = _engine_with_rows({"id": USER_ID, "organization_id": ORG_ID}, None)
    settings = MagicMock()
    settings.public_url = "https://192.168.1.51"
    with (
        patch("app.admin_activation.engine", engine),
        patch("app.admin_activation.get_settings", return_value=settings),
        patch("app.admin_activation.random_token", return_value="one-time-token"),
    ):
        url = issue("admin_reset")
    assert url == "https://192.168.1.51/#activation=one-time-token"
    with pytest.raises(ValueError):
        issue("invalid")
