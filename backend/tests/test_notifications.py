from unittest.mock import MagicMock, patch
from uuid import UUID

from starlette.requests import Request

from app.routers.notifications import NotificationKeys, dismiss, list_notifications, mark_read
from app.security import SecurityContext, token_hash

USER = UUID("60000000-0000-4000-8000-000000000002")
ORG = UUID("10000000-0000-4000-8000-000000000001")


def context() -> SecurityContext:
    return SecurityContext(USER, ORG, "professionnel", "Alex Bernard", None, token_hash("csrf"))


def request() -> Request:
    return Request(
        {"type": "http", "headers": [(b"origin", b"https://localhost"), (b"x-csrf-token", b"csrf")]}
    )


def database(connection: MagicMock, transaction: bool = False) -> MagicMock:
    value = MagicMock()
    manager = value.begin if transaction else value.connect
    manager.return_value.__enter__.return_value = connection
    return value


def test_notification_list_counts_only_unread_items() -> None:
    result = MagicMock()
    result.mappings.return_value.__iter__.return_value = iter([
        {"notification_key": "task:1", "title": "Tache en retard", "is_read": False},
        {"notification_key": "task:2", "title": "Echeance proche", "is_read": True},
    ])
    connection = MagicMock()
    connection.execute.return_value = result
    with patch("app.routers.notifications.engine", database(connection)), patch(
        "app.routers.notifications.require_permission"
    ):
        response = list_notifications(context())
    assert response["unread_count"] == 1
    assert len(response["items"]) == 2


def test_notification_read_and_dismiss_are_personal() -> None:
    connection = MagicMock()
    with patch("app.routers.notifications.engine", database(connection, True)), patch(
        "app.routers.notifications.require_permission"
    ):
        mark_read(NotificationKeys(keys=["task:1"]), request(), context())
        dismiss(NotificationKeys(keys=["task:1"]), request(), context())
    assert connection.execute.call_count == 2
    assert all(call.args[1]["user_id"] == USER for call in connection.execute.call_args_list)
