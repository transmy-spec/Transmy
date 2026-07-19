from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID

from starlette.requests import Request
from starlette.responses import Response

from app.routers.work import (
    AssignmentInput,
    HandoverCreate,
    HandoverItemInput,
    TaskCreate,
    TaskUpdate,
    add_handover_item,
    assign_task,
    close_handover,
    complete_task,
    create_handover,
    create_task,
    get_handover,
    get_task,
    list_handovers,
    list_tasks,
    open_handover,
    task_events,
    update_task,
)
from app.security import SecurityContext, token_hash

USER = UUID("60000000-0000-4000-8000-000000000003")
ORG = UUID("10000000-0000-4000-8000-000000000001")
UNIT = UUID("40000000-0000-4000-8000-000000000001")
TASK = UUID("e0000000-0000-4000-8000-000000000001")
HANDOVER = UUID("f0000000-0000-4000-8000-000000000001")


def ctx() -> SecurityContext:
    return SecurityContext(USER, ORG, "chefservice", "Sophie Laurent", None, token_hash("csrf"))


def req() -> Request:
    return Request(
        {"type": "http", "headers": [(b"origin", b"https://localhost"), (b"x-csrf-token", b"csrf")]}
    )


def result(row=None, rows=None):
    value = MagicMock()
    mapped = value.mappings.return_value
    mapped.first.return_value = row
    mapped.one.return_value = row
    mapped.__iter__.return_value = iter(rows or ([] if row is None else [row]))
    value.first.return_value = row
    return value


def db(connection, transaction=False):
    value = MagicMock()
    manager = value.begin if transaction else value.connect
    manager.return_value.__enter__.return_value = connection
    return value


def task_row(**changes):
    row = {"id": TASK, "status": "todo", "row_version": 1, "title": "Appeler le service"}
    row.update(changes)
    return row


def handover_row(**changes):
    row = {"id": HANDOVER, "status": "draft", "row_version": 1, "unit_name": "Unite A"}
    row.update(changes)
    return row


def test_task_list_create_get_update_assign_complete_and_events() -> None:
    connection = MagicMock()
    connection.execute.return_value = result(rows=[task_row()])
    with (
        patch("app.routers.work.engine", db(connection)),
        patch("app.routers.work.require_permission"),
    ):
        assert list_tasks(ctx())["items"][0]["title"] == "Appeler le service"
    connection = MagicMock()
    connection.execute.side_effect = [
        result((UNIT,)),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    payload = TaskCreate(title="Appeler le service", due_at=datetime.now(UTC) + timedelta(days=1))
    with (
        patch("app.routers.work.engine", db(connection, True)),
        patch("app.routers.work.require_permission"),
    ):
        assert create_task(payload, req(), Response(), ctx())["status"] == "todo"
    connection = MagicMock()
    connection.execute.return_value = result(task_row())
    with (
        patch("app.routers.work.engine", db(connection)),
        patch("app.routers.work.require_permission"),
    ):
        assert get_task(TASK, Response(), ctx())["id"] == TASK
    connection = MagicMock()
    connection.execute.side_effect = [
        result(task_row()),
        result(task_row(status="in_progress", row_version=2)),
        MagicMock(),
        MagicMock(),
    ]
    with (
        patch("app.routers.work.engine", db(connection, True)),
        patch("app.routers.work.require_permission"),
    ):
        assert (
            update_task(TASK, TaskUpdate(status="in_progress"), req(), Response(), ctx(), '"1"')[
                "row_version"
            ]
            == 2
        )
    connection = MagicMock()
    connection.execute.side_effect = [
        result(task_row()),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    with (
        patch("app.routers.work.engine", db(connection, True)),
        patch("app.routers.work.require_permission"),
    ):
        assert assign_task(TASK, AssignmentInput(user_id=USER), req(), ctx())["assigned_to"] == str(
            USER
        )
    connection = MagicMock()
    connection.execute.side_effect = [
        result(task_row()),
        result({"status": "done", "row_version": 2}),
        MagicMock(),
        MagicMock(),
    ]
    with (
        patch("app.routers.work.engine", db(connection, True)),
        patch("app.routers.work.require_permission"),
    ):
        assert complete_task(TASK, req(), Response(), ctx(), '"1"')["status"] == "done"
    connection = MagicMock()
    connection.execute.side_effect = [
        result(task_row()),
        result(rows=[{"event_type": "task.created"}]),
    ]
    with (
        patch("app.routers.work.engine", db(connection)),
        patch("app.routers.work.require_permission"),
    ):
        assert task_events(TASK, ctx())["items"][0]["event_type"] == "task.created"


def test_handover_create_list_detail_item_open_and_close() -> None:
    now = datetime.now(UTC)
    connection = MagicMock()
    connection.execute.side_effect = [
        result((UNIT,)),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    with (
        patch("app.routers.work.engine", db(connection, True)),
        patch("app.routers.work.require_permission"),
    ):
        assert (
            create_handover(
                HandoverCreate(period_start=now, period_end=now + timedelta(hours=8)),
                req(),
                Response(),
                ctx(),
            )["status"]
            == "draft"
        )
    connection = MagicMock()
    connection.execute.return_value = result(rows=[handover_row()])
    with (
        patch("app.routers.work.engine", db(connection)),
        patch("app.routers.work.require_permission"),
    ):
        assert list_handovers(ctx())["items"][0]["unit_name"] == "Unite A"
    connection = MagicMock()
    connection.execute.side_effect = [
        result(handover_row()),
        result(rows=[task_row()]),
        result(rows=[]),
    ]
    with (
        patch("app.routers.work.engine", db(connection)),
        patch("app.routers.work.require_permission"),
    ):
        assert len(get_handover(HANDOVER, Response(), ctx())["tasks"]) == 1
    connection = MagicMock()
    connection.execute.side_effect = [result(handover_row()), MagicMock()]
    with (
        patch("app.routers.work.engine", db(connection, True)),
        patch("app.routers.work.require_permission"),
    ):
        assert (
            add_handover_item(
                HANDOVER,
                HandoverItemInput(item_type="task", item_id=TASK, reason="A suivre"),
                req(),
                ctx(),
            )["item_type"]
            == "task"
        )
    connection = MagicMock()
    connection.execute.side_effect = [
        result(handover_row()),
        result({"status": "open", "row_version": 2}),
        MagicMock(),
    ]
    with (
        patch("app.routers.work.engine", db(connection, True)),
        patch("app.routers.work.require_permission"),
    ):
        assert open_handover(HANDOVER, req(), Response(), ctx(), '"1"')["status"] == "open"
    connection = MagicMock()
    connection.execute.side_effect = [
        result(handover_row(status="open", row_version=2)),
        result({"status": "closed", "row_version": 3}),
        MagicMock(),
    ]
    with (
        patch("app.routers.work.engine", db(connection, True)),
        patch("app.routers.work.require_permission"),
    ):
        assert close_handover(HANDOVER, req(), Response(), ctx(), '"2"')["status"] == "closed"
