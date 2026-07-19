from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.routers.transmissions import (
    CorrectionInput,
    DraftUpdate,
    TransmissionCreate,
    _hash,
    acknowledge,
    correct,
    create_transmission,
    get_transmission,
    list_transmissions,
    publish,
    references,
    update_draft,
)
from app.security import SecurityContext, token_hash

USER_ID = UUID("60000000-0000-4000-8000-000000000002")
ORG_ID = UUID("10000000-0000-4000-8000-000000000001")
PERSON_ID = UUID("90000000-0000-4000-8000-000000000001")
UNIT_ID = UUID("40000000-0000-4000-8000-000000000001")
TRANSMISSION_ID = UUID("c0000000-0000-4000-8000-000000000001")
VERSION_ID = UUID("d0000000-0000-4000-8000-000000000001")
CATEGORY_ID = UUID("a0000000-0000-4000-8000-000000000001")
IMPORTANCE_ID = UUID("b0000000-0000-4000-8000-000000000001")


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


def _result(
    row: dict[str, object] | None = None, rows: list[dict[str, object]] | None = None
) -> MagicMock:
    result = MagicMock()
    mapping = result.mappings.return_value
    mapping.first.return_value = row
    mapping.one.return_value = row
    mapping.__iter__.return_value = iter(rows or ([] if row is None else [row]))
    result.first.return_value = None if row is None else (1,)
    return result


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": TRANSMISSION_ID,
        "person_id": PERSON_ID,
        "unit_id": UNIT_ID,
        "status": "draft",
        "author_id": USER_ID,
        "row_version": 1,
        "version_id": VERSION_ID,
        "version_number": 1,
        "content": "Observation utile",
        "acknowledged": False,
    }
    row.update(changes)
    return row


def test_hash_references_and_lists() -> None:
    assert len(_hash("contenu")) == 64
    connection = MagicMock()
    connection.execute.side_effect = [
        _result(rows=[{"id": CATEGORY_ID, "label": "Vie quotidienne"}]),
        _result(rows=[{"id": IMPORTANCE_ID, "label": "Normale"}]),
    ]
    with (
        patch("app.routers.transmissions.engine", _database(connection)),
        patch("app.routers.transmissions.require_permission"),
    ):
        payload = references(_context())
    assert payload["categories"][0]["label"] == "Vie quotidienne"
    connection = MagicMock()
    connection.execute.return_value = _result(rows=[_row()])
    with (
        patch("app.routers.transmissions.engine", _database(connection)),
        patch("app.routers.transmissions.require_permission"),
    ):
        payload = list_transmissions(_context(), "draft", PERSON_ID)
    assert payload["items"][0]["content"] == "Observation utile"


def test_create_and_get_transmission() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [
        _result({"unit_id": UNIT_ID}),
        _result({"ok": True}),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    response = Response()
    with (
        patch("app.routers.transmissions.engine", _database(connection, True)),
        patch("app.routers.transmissions.require_permission"),
    ):
        payload = create_transmission(
            TransmissionCreate(
                person_id=PERSON_ID,
                category_id=CATEGORY_ID,
                importance_level_id=IMPORTANCE_ID,
                content=" Observation utile ",
            ),
            _request(),
            response,
            _context(),
        )
    assert payload["status"] == "draft" and response.headers["etag"] == '"1"'
    connection = MagicMock()
    connection.execute.return_value = _result(_row())
    response = Response()
    with (
        patch("app.routers.transmissions.engine", _database(connection)),
        patch("app.routers.transmissions.require_permission"),
    ):
        payload = get_transmission(TRANSMISSION_ID, response, _context())
    assert payload["version_number"] == 1


def test_update_and_publish_draft() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [
        _result(_row()),
        _result({"row_version": 2}),
        MagicMock(),
        MagicMock(),
    ]
    response = Response()
    with (
        patch("app.routers.transmissions.engine", _database(connection, True)),
        patch("app.routers.transmissions.require_permission"),
    ):
        payload = update_draft(
            TRANSMISSION_ID,
            DraftUpdate(content="Nouveau contenu"),
            _request(),
            response,
            _context(),
            '"1"',
        )
    assert payload["row_version"] == 2
    connection = MagicMock()
    connection.execute.side_effect = [
        _result(_row()),
        _result({"status": "published", "row_version": 2}),
        MagicMock(),
    ]
    with (
        patch("app.routers.transmissions.engine", _database(connection, True)),
        patch("app.routers.transmissions.require_permission"),
    ):
        payload = publish(TRANSMISSION_ID, _request(), Response(), _context(), '"1"')
    assert payload["status"] == "published"


def test_correction_and_acknowledgement_are_append_only() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [
        _result(_row(status="published")),
        MagicMock(),
        _result({"row_version": 3}),
        MagicMock(),
    ]
    with (
        patch("app.routers.transmissions.engine", _database(connection, True)),
        patch("app.routers.transmissions.require_permission"),
    ):
        payload = correct(
            TRANSMISSION_ID,
            CorrectionInput(content="Version corrigee", reason="Precision necessaire"),
            _request(),
            Response(),
            _context(),
        )
    assert payload["version_number"] == 2
    connection = MagicMock()
    connection.execute.side_effect = [
        _result(
            _row(
                status="published",
                author_id=UUID("60000000-0000-4000-8000-000000000003"),
            )
        ),
        MagicMock(),
        MagicMock(),
    ]
    with (
        patch("app.routers.transmissions.engine", _database(connection, True)),
        patch("app.routers.transmissions.require_permission"),
    ):
        payload = acknowledge(TRANSMISSION_ID, _request(), _context())
    assert payload["acknowledged"] is True


def test_author_does_not_acknowledge_own_transmission() -> None:
    connection = MagicMock()
    connection.execute.return_value = _result(_row(status="published", author_id=USER_ID))
    with (
        patch("app.routers.transmissions.engine", _database(connection, True)),
        patch("app.routers.transmissions.require_permission"),
        pytest.raises(HTTPException) as error,
    ):
        acknowledge(TRANSMISSION_ID, _request(), _context())
    assert error.value.status_code == 409
