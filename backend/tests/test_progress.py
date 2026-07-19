# ruff: noqa: E501
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import Response
from pydantic import SecretStr
from starlette.requests import Request

from app.crypto import encrypt_json
from app.routers.progress import (
    GoalInput,
    ReviewInput,
    create_goal,
    list_goals,
    review_event,
    update_goal,
)
from app.security import SecurityContext, token_hash

USER = UUID("60000000-0000-4000-8000-000000000003")
ORG = UUID("10000000-0000-4000-8000-000000000001")
PERSON = UUID("90000000-0000-4000-8000-000000000001")
GOAL = UUID("a1000000-0000-4000-8000-000000000001")
EVENT = UUID("a2000000-0000-4000-8000-000000000001")


def context() -> SecurityContext:
    return SecurityContext(USER, ORG, "chef", "Sophie", None, token_hash("csrf"))


def request() -> Request:
    return Request({"type": "http", "headers": [(b"origin", b"https://localhost"),
      (b"x-csrf-token", b"csrf")]})


def database(connection: MagicMock) -> MagicMock:
    value = MagicMock()
    value.begin.return_value.__enter__.return_value = connection
    return value


def settings() -> object:
    return type("Settings", (), {"field_encryption_key": SecretStr("a" * 32)})()


def test_goal_list_create_and_update() -> None:
    with patch("app.crypto.get_settings", return_value=settings()):
        encrypted = encrypt_json({"title": "Autonomie", "success_criteria": "Trajet seul",
          "person_feedback": "D accord"}, GOAL.bytes)
    rows = MagicMock()
    rows.mappings.return_value.__iter__.return_value = iter([{"id": GOAL,
      "encrypted_payload": encrypted, "progress": 20}])
    connection = MagicMock()
    connection.execute.side_effect = [rows, MagicMock()]
    with patch("app.routers.progress.engine", database(connection)), patch(
      "app.routers.progress.require_permission"), patch(
      "app.crypto.get_settings", return_value=settings()):
        assert list_goals(PERSON, context())["items"][0]["title"] == "Autonomie"

    connection = MagicMock()
    connection.execute.side_effect = [MagicMock(first=lambda: (UUID(int=4),)), MagicMock(), MagicMock()]
    payload = GoalInput(title="Autonomie", progress=25)
    with patch("app.routers.progress.engine", database(connection)), patch(
      "app.routers.progress.require_permission"), patch(
      "app.crypto.get_settings", return_value=settings()):
        assert create_goal(PERSON, payload, request(), Response(), context())["row_version"] == 1

    updated = MagicMock()
    updated.mappings.return_value.first.return_value = {"id": GOAL, "row_version": 2}
    connection = MagicMock()
    connection.execute.side_effect = [updated, MagicMock()]
    with patch("app.routers.progress.engine", database(connection)), patch(
      "app.routers.progress.require_permission"), patch(
      "app.crypto.get_settings", return_value=settings()):
        assert update_goal(PERSON, GOAL, payload, request(), Response(), context(), '"1"')["row_version"] == 2


def test_event_review_is_encrypted_and_audited() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [MagicMock(first=lambda: (EVENT,)), MagicMock(), MagicMock(), MagicMock()]
    with patch("app.routers.progress.engine", database(connection)), patch(
      "app.routers.progress.require_permission"), patch(
      "app.crypto.get_settings", return_value=settings()):
        result = review_event(EVENT, ReviewInput(summary="Sortie realisee",
          attendee_ids=[PERSON]), request(), context())
    assert result["row_version"] == 1
    assert connection.execute.call_count == 4
