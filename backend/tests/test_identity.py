from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers.identity import (
    MembershipInput,
    NameInput,
    ReasonInput,
    UserInvitationInput,
    UserStatusInput,
    add_membership,
    audit_events,
    create_unit,
    invite_user,
    renew_user_invitation,
    revoke_user_invitation,
    session,
    structure,
    update_user_status,
    user_detail,
    users,
)
from app.security import SecurityContext, token_hash


def _context() -> SecurityContext:
    return SecurityContext(
        user_id=UUID("60000000-0000-4000-8000-000000000001"),
        organization_id=UUID("10000000-0000-4000-8000-000000000001"),
        username="admin",
        display_name="Camille Martin",
        email="admin@transmissions.test",
        csrf_hash=token_hash("csrf-token"),
    )


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "headers": [
                (b"origin", b"https://localhost"),
                (b"x-csrf-token", b"csrf-token"),
                (b"cookie", b"transmissions_csrf=csrf-token"),
            ],
        }
    )


def _mapping_result(rows: list[dict[str, object]]) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.__iter__.return_value = iter(rows)
    return result


def test_session_returns_profile_roles_permissions_and_contexts() -> None:
    with (
        patch(
            "app.routers.identity._roles",
            return_value=[{"code": "organization_admin", "label": "Administrateur"}],
        ),
        patch("app.routers.identity._contexts", return_value=[]),
        patch("app.routers.identity.permissions_for", return_value={"structure.manage"}),
    ):
        payload = session(_request(), _context())
    assert payload["user"]["username"] == "admin"
    assert payload["permissions"] == ["structure.manage"]
    assert payload["csrf_token"] == "csrf-token"


def test_role_and_context_queries_are_exercised_through_session() -> None:
    roles_result = _mapping_result([{"code": "professional", "label": "Professionnel"}])
    contexts_result = _mapping_result([{"id": UUID(int=1), "name": "Unité A"}])
    connection = MagicMock()
    connection.execute.side_effect = [roles_result, contexts_result]
    database = MagicMock()
    database.connect.return_value.__enter__.return_value = connection
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.permissions_for", return_value=set()),
    ):
        payload = session(_request(), _context())
    assert payload["roles"][0]["code"] == "professional"
    assert payload["contexts"][0]["name"] == "Unité A"


def test_structure_and_users_return_scoped_rows() -> None:
    organization_result = MagicMock()
    organization_result.mappings.return_value.one.return_value = {
        "id": _context().organization_id,
        "name": "Association Horizon",
        "status": "active",
    }
    structure_result = _mapping_result([{"unit_name": "Unité A"}])
    users_result = _mapping_result([{"username": "admin"}])
    connection = MagicMock()
    connection.execute.side_effect = [organization_result, structure_result, users_result]
    database = MagicMock()
    database.connect.return_value.__enter__.return_value = connection
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.require_permission"),
    ):
        structure_payload = structure(_context())
        users_payload = users(_context())
    assert structure_payload["items"][0]["unit_name"] == "Unité A"
    assert users_payload["items"][0]["username"] == "admin"


def test_create_unit_checks_scope_writes_and_audits() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [
        MagicMock(first=lambda: (UUID(int=1),)),
        MagicMock(),
        MagicMock(),
    ]
    database = MagicMock()
    database.begin.return_value.__enter__.return_value = connection
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.require_permission"),
    ):
        payload = create_unit(UUID(int=1), NameInput(name="Unité B"), _request(), _context())
    assert payload["name"] == "Unité B"
    assert connection.execute.call_count == 3


def test_create_unit_hides_unknown_service() -> None:
    connection = MagicMock()
    connection.execute.return_value.first.return_value = None
    database = MagicMock()
    database.begin.return_value.__enter__.return_value = connection
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.require_permission"),
        pytest.raises(HTTPException) as error,
    ):
        create_unit(UUID(int=1), NameInput(name="Unité B"), _request(), _context())
    assert error.value.status_code == 404


def test_audit_events_returns_recent_events() -> None:
    database = MagicMock()
    database.connect.return_value.__enter__.return_value.execute.return_value = _mapping_result(
        [{"id": 1, "event_type": "session.login"}]
    )
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.require_permission"),
    ):
        payload = audit_events(_context())
    assert payload["items"][0]["event_type"] == "session.login"


def test_user_detail_status_and_membership_management() -> None:
    target = UUID("60000000-0000-4000-8000-000000000002")
    unit = UUID("40000000-0000-4000-8000-000000000001")
    user_result = MagicMock()
    user_result.mappings.return_value.first.return_value = {
        "id": target,
        "username": "professionnel",
        "status": "active",
    }
    connection = MagicMock()
    connection.execute.side_effect = [user_result, _mapping_result([{"unit_name": "Unite A"}])]
    database = MagicMock()
    database.connect.return_value.__enter__.return_value = connection
    with patch("app.routers.identity.engine", database), patch(
        "app.routers.identity.require_permission"
    ):
        assert user_detail(target, _context())["memberships"][0]["unit_name"] == "Unite A"

    updated = MagicMock()
    updated.mappings.return_value.first.return_value = {"id": target, "status": "disabled"}
    connection = MagicMock()
    connection.execute.side_effect = [updated, MagicMock(), MagicMock()]
    database = MagicMock()
    database.begin.return_value.__enter__.return_value = connection
    with patch("app.routers.identity.engine", database), patch(
        "app.routers.identity.require_permission"
    ):
        response = update_user_status(
            target, UserStatusInput(status="disabled", reason="Depart du service"),
            _request(), _context(),
        )
    assert response["status"] == "disabled"

    connection = MagicMock()
    connection.execute.side_effect = [
        MagicMock(first=lambda: (1,)),
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
    ]
    database = MagicMock()
    database.begin.return_value.__enter__.return_value = connection
    with patch("app.routers.identity.engine", database), patch(
        "app.routers.identity.require_permission"
    ):
        response = add_membership(target, MembershipInput(unit_id=unit, is_primary=True),
                                  _request(), _context())
    assert response["unit_id"] == str(unit)


def test_invite_user_provisions_identity_membership_role_and_ticket() -> None:
    target = UUID("90000000-0000-4000-8000-000000000001")
    unit = UUID("40000000-0000-4000-8000-000000000001")
    role = UUID("50000000-0000-4000-8000-000000000002")
    scope_result = MagicMock()
    scope_result.mappings.return_value.first.return_value = {"unit_id": unit, "role_id": role}
    scope_connection = MagicMock()
    scope_connection.execute.return_value = scope_result
    write_connection = MagicMock()
    database = MagicMock()
    database.connect.return_value.__enter__.return_value = scope_connection
    database.begin.return_value.__enter__.return_value = write_connection
    settings = MagicMock()
    settings.oidc_issuer = "https://local/oidc/realms/transmissions"
    settings.public_url = "https://local"
    payload = UserInvitationInput(
        username="lea.martin",
        display_name="Lea Martin",
        email="lea@example.test",
        role_code="professional",
        unit_id=unit,
    )
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.require_permission"),
        patch("app.routers.identity.create_user", return_value=target),
        patch("app.routers.identity.random_token", return_value="invitation-token"),
        patch("app.routers.identity.get_settings", return_value=settings),
    ):
        result = invite_user(payload, _request(), _context())
    assert result["id"] == str(target)
    assert result["activation_url"] == "https://local/#activation=invitation-token"
    assert write_connection.execute.call_count == 3


def test_invitation_conflict_renewal_and_revocation() -> None:
    from app.keycloak_admin import KeycloakUserConflictError

    unit = UUID("40000000-0000-4000-8000-000000000001")
    scope_result = MagicMock()
    scope_result.mappings.return_value.first.return_value = {
        "unit_id": unit,
        "role_id": UUID(int=2),
    }
    connection = MagicMock()
    connection.execute.return_value = scope_result
    database = MagicMock()
    database.connect.return_value.__enter__.return_value = connection
    payload = UserInvitationInput(
        username="deja.pris",
        display_name="Compte Existant",
        email="existing@example.test",
        role_code="professional",
        unit_id=unit,
    )
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.require_permission"),
        patch("app.routers.identity.create_user", side_effect=KeycloakUserConflictError),
        pytest.raises(HTTPException) as error,
    ):
        invite_user(payload, _request(), _context())
    assert error.value.status_code == 409

    target = UUID("90000000-0000-4000-8000-000000000001")
    active = MagicMock()
    active.first.return_value = (target,)
    write_connection = MagicMock()
    write_connection.execute.side_effect = [active, MagicMock(), MagicMock()]
    database = MagicMock()
    database.begin.return_value.__enter__.return_value = write_connection
    settings = MagicMock()
    settings.public_url = "https://local"
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.require_permission"),
        patch("app.routers.identity.random_token", return_value="renewed"),
        patch("app.routers.identity.get_settings", return_value=settings),
    ):
        renewed = renew_user_invitation(target, _request(), _context())
    assert renewed["activation_url"].endswith("#activation=renewed")

    revoked = MagicMock()
    revoked.first.return_value = (target,)
    write_connection = MagicMock()
    write_connection.execute.side_effect = [revoked, MagicMock()]
    database.begin.return_value.__enter__.return_value = write_connection
    with (
        patch("app.routers.identity.engine", database),
        patch("app.routers.identity.require_permission"),
    ):
        revoke_user_invitation(
            target, ReasonInput(reason="Invitation remise par erreur"), _request(), _context()
        )
