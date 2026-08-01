from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.routers.people import (
    ArchiveInput,
    AssignmentInput,
    PersonCreate,
    PersonUpdate,
    TransferInput,
    _can_use_unit,
    _etag,
    _parse_if_match,
    archive_person,
    create_assignment,
    create_person,
    get_person,
    list_authorized_units,
    list_people,
    transfer_person,
    update_person,
)
from app.security import SecurityContext, token_hash

USER_ID = UUID("60000000-0000-4000-8000-000000000002")
ORG_ID = UUID("10000000-0000-4000-8000-000000000001")
UNIT_ID = UUID("40000000-0000-4000-8000-000000000001")
OTHER_UNIT_ID = UUID("40000000-0000-4000-8000-000000000002")
ASSIGNMENT_ID = UUID("91000000-0000-4000-8000-000000000001")
PERSON_ID = UUID("90000000-0000-4000-8000-000000000001")


def _context() -> SecurityContext:
    return SecurityContext(
        USER_ID, ORG_ID, "professionnel", "Alex Bernard", None, token_hash("csrf")
    )


def _request() -> Request:
    return Request(
        {"type": "http", "headers": [(b"origin", b"https://localhost"), (b"x-csrf-token", b"csrf")]}
    )


def _database(connection: MagicMock, transaction: bool = False) -> MagicMock:
    database = MagicMock()
    manager = database.begin if transaction else database.connect
    manager.return_value.__enter__.return_value = connection
    return database


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": PERSON_ID,
        "internal_reference": "HZN-0001",
        "family_name": "Moreau",
        "given_name": "Lina",
        "preferred_name": None,
        "birth_date": None,
        "status": "active",
        "row_version": 1,
        "unit_id": UNIT_ID,
        "unit_name": "Unite A",
        "service_name": "Service",
        "establishment_name": "Etablissement",
    }
    row.update(changes)
    return row


def test_etag_validation_and_person_update_validation() -> None:
    assert _etag(3) == '"3"'
    assert _parse_if_match('"3"') == 3
    with pytest.raises(HTTPException) as missing:
        _parse_if_match(None)
    assert missing.value.status_code == 428
    with pytest.raises(HTTPException) as invalid:
        _parse_if_match("oops")
    assert invalid.value.status_code == 400
    with pytest.raises(ValueError):
        PersonUpdate()


def test_unit_scope_check() -> None:
    connection = MagicMock()
    connection.execute.return_value.first.return_value = (1,)
    with patch("app.routers.people.engine", _database(connection)):
        assert _can_use_unit(_context(), UNIT_ID, "person.update")
    assert connection.execute.call_args.args[1]["permission"] == "person.update"
    connection.execute.return_value.first.return_value = None
    with patch("app.routers.people.engine", _database(connection)):
        assert not _can_use_unit(_context(), UNIT_ID, "person.update")


def test_authorized_units_uses_requested_permission_scope() -> None:
    result = MagicMock()
    result.mappings.return_value.__iter__.return_value = iter(
        [
            {
                "id": UNIT_ID,
                "name": "Unité A",
                "service_name": "Horizon",
                "establishment_name": "Les Amandiers",
            }
        ]
    )
    connection = MagicMock()
    connection.execute.return_value = result
    with (
        patch("app.routers.people.engine", _database(connection)),
        patch("app.routers.people.require_permission") as require,
    ):
        payload = list_authorized_units(_context(), "person.create")
    assert payload["items"][0]["id"] == UNIT_ID
    assert connection.execute.call_args.args[1]["permission"] == "person.create"
    require.assert_called_once_with(_context(), "person.create")


def test_list_people_searches_scope_and_protects_archives() -> None:
    result = MagicMock()
    result.mappings.return_value.__iter__.return_value = iter([_row()])
    connection = MagicMock()
    connection.execute.return_value = result
    with (
        patch("app.routers.people.engine", _database(connection)),
        patch("app.routers.people.require_permission"),
    ):
        payload = list_people(_context(), "Lin", "active")
    assert payload["items"][0]["given_name"] == "Lina"
    assert "ILIKE" in str(connection.execute.call_args.args[0])
    with (
        patch("app.routers.people.require_permission"),
        patch("app.routers.people.permissions_for", return_value=set()),
        pytest.raises(HTTPException) as denied,
    ):
        list_people(_context(), None, "archived")
    assert denied.value.status_code == 403


def test_create_person_writes_assignment_and_audit() -> None:
    connection = MagicMock()
    response = Response()
    payload = PersonCreate(family_name=" Moreau ", given_name=" Lina ", unit_id=UNIT_ID)
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
        patch("app.routers.people._can_use_unit", return_value=True),
    ):
        created = create_person(payload, _request(), response, _context())
    assert created["internal_reference"].startswith("HZN-")
    assert response.headers["etag"] == '"1"'
    assert connection.execute.call_count == 3
    audit_metadata = connection.execute.call_args_list[2].args[1]["metadata"]
    assert str(UNIT_ID) in audit_metadata
    assert "assignment_id" in audit_metadata
    with (
        patch("app.routers.people.require_permission"),
        patch("app.routers.people._can_use_unit", return_value=False),
        pytest.raises(HTTPException) as hidden,
    ):
        create_person(payload, _request(), Response(), _context())
    assert hidden.value.status_code == 404


def test_get_person_audits_and_hides_unreadable_archive() -> None:
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.first.return_value = _row()
    response = Response()
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
    ):
        payload = get_person(PERSON_ID, response, _context())
    assert payload["internal_reference"] == "HZN-0001"
    assert response.headers["etag"] == '"1"'
    connection.execute.return_value.mappings.return_value.first.return_value = _row(
        status="archived"
    )
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
        patch("app.routers.people.permissions_for", return_value=set()),
        pytest.raises(HTTPException) as hidden,
    ):
        get_person(PERSON_ID, Response(), _context())
    assert hidden.value.status_code == 404


def test_update_person_checks_version_and_returns_new_etag() -> None:
    connection = MagicMock()
    updated = _row(family_name="Durand", row_version=2)
    scoped_result = MagicMock()
    scoped_result.first.return_value = (PERSON_ID,)
    update_result = MagicMock()
    update_result.mappings.return_value.first.return_value = updated
    connection.execute.side_effect = [scoped_result, update_result, MagicMock()]
    response = Response()
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
    ):
        payload = update_person(
            PERSON_ID, PersonUpdate(family_name="Durand"), _request(), response, _context(), '"1"'
        )
    assert payload["row_version"] == 2
    assert response.headers["etag"] == '"2"'
    connection.execute.side_effect = [
        scoped_result,
        MagicMock(mappings=lambda: MagicMock(first=lambda: None)),
    ]
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
        pytest.raises(HTTPException) as conflict,
    ):
        update_person(
            PERSON_ID, PersonUpdate(given_name="Lucie"), _request(), Response(), _context(), '"1"'
        )
    assert conflict.value.status_code == 412


def test_transfer_person_closes_active_assignments_and_audits() -> None:
    scoped = MagicMock()
    scoped.mappings.return_value.first.return_value = _row(row_version=1)
    version = MagicMock()
    version.mappings.return_value.first.return_value = {"row_version": 2}
    assignments = MagicMock()
    assignments.mappings.return_value.__iter__.return_value = iter(
        [{"id": ASSIGNMENT_ID, "unit_id": UNIT_ID, "is_primary": True}]
    )
    connection = MagicMock()
    connection.execute.side_effect = [
        scoped,
        version,
        assignments,
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    response = Response()
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
        patch("app.routers.people._can_use_unit", return_value=True),
    ):
        payload = transfer_person(
            PERSON_ID,
            TransferInput(unit_id=OTHER_UNIT_ID, reason="Changement de groupe"),
            _request(),
            response,
            _context(),
            '"1"',
        )

    assert payload["unit_id"] == str(OTHER_UNIT_ID)
    assert connection.execute.call_args_list[0].args[1]["scope_permission"] == "person.update"
    assert payload["row_version"] == 2
    assert response.headers["etag"] == '"2"'
    assert "ends_at = now()" in str(connection.execute.call_args_list[3].args[0])
    assert "INSERT INTO app.person_assignment" in str(connection.execute.call_args_list[4].args[0])
    audit_metadata = connection.execute.call_args_list[5].args[1]["metadata"]
    assert str(UNIT_ID) in audit_metadata
    assert str(OTHER_UNIT_ID) in audit_metadata
    assert str(payload["id"]) in audit_metadata
    assert "Changement de groupe" in audit_metadata


def test_transfer_person_rejects_current_unit() -> None:
    scoped = MagicMock()
    scoped.mappings.return_value.first.return_value = _row(row_version=1)
    version = MagicMock()
    version.mappings.return_value.first.return_value = {"row_version": 2}
    assignments = MagicMock()
    assignments.mappings.return_value.__iter__.return_value = iter(
        [{"id": ASSIGNMENT_ID, "unit_id": UNIT_ID, "is_primary": True}]
    )
    connection = MagicMock()
    connection.execute.side_effect = [scoped, version, assignments]
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
        patch("app.routers.people._can_use_unit", return_value=True),
        pytest.raises(HTTPException) as conflict,
    ):
        transfer_person(
            PERSON_ID,
            TransferInput(unit_id=UNIT_ID, reason="Même unité"),
            _request(),
            Response(),
            _context(),
            '"1"',
        )
    assert conflict.value.status_code == 409
    assert connection.execute.call_count == 3


def test_transfer_person_rejects_stale_version() -> None:
    scoped = MagicMock()
    scoped.mappings.return_value.first.return_value = _row(row_version=2)
    stale_version = MagicMock()
    stale_version.mappings.return_value.first.return_value = None
    connection = MagicMock()
    connection.execute.side_effect = [scoped, stale_version]
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
        patch("app.routers.people._can_use_unit", return_value=True),
        pytest.raises(HTTPException) as conflict,
    ):
        transfer_person(
            PERSON_ID,
            TransferInput(unit_id=OTHER_UNIT_ID, reason="Changement devenu obsolète"),
            _request(),
            Response(),
            _context(),
            '"1"',
        )
    assert conflict.value.status_code == 412
    assert connection.execute.call_count == 2


def test_create_assignment_and_archive() -> None:
    connection = MagicMock()
    scoped = MagicMock()
    scoped.first.return_value = (PERSON_ID,)
    connection.execute.side_effect = [scoped, MagicMock(), MagicMock(), MagicMock()]
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
        patch("app.routers.people._can_use_unit", return_value=True),
    ):
        assignment = create_assignment(
            PERSON_ID, AssignmentInput(unit_id=UNIT_ID, is_primary=True), _request(), _context()
        )
    assert assignment["person_id"] == str(PERSON_ID)
    assert connection.execute.call_count == 4

    connection = MagicMock()
    archived = MagicMock()
    archived.mappings.return_value.first.return_value = _row(status="archived", row_version=2)
    connection.execute.side_effect = [scoped, archived, MagicMock()]
    response = Response()
    with (
        patch("app.routers.people.engine", _database(connection, True)),
        patch("app.routers.people.require_permission"),
    ):
        payload = archive_person(
            PERSON_ID, ArchiveInput(reason="Fin de suivi"), _request(), response, _context(), '"1"'
        )
    assert payload["status"] == "archived"
    assert response.headers["etag"] == '"2"'
