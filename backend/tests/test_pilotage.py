from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.routers.pilotage import get_indicators
from app.security import SecurityContext, token_hash


def context() -> SecurityContext:
    return SecurityContext(
        UUID("60000000-0000-4000-8000-000000000003"),
        UUID("10000000-0000-4000-8000-000000000001"),
        "chefservice", "Sophie Laurent", None, token_hash("csrf"),
    )


def test_pilotage_rejects_unbounded_period() -> None:
    with patch("app.routers.pilotage.require_permission"), pytest.raises(
        HTTPException
    ) as error:
        get_indicators(context(), 365)
    assert error.value.status_code == 422


def test_pilotage_returns_aggregates_and_daily_activity() -> None:
    summary = MagicMock()
    summary.mappings.return_value.one.return_value = {
        "active_people": 4, "transmissions": 8, "urgent_transmissions": 2,
        "tasks_created": 5, "tasks_completed": 4, "tasks_overdue": 1,
    }
    daily = MagicMock()
    daily.mappings.return_value.__iter__.return_value = iter([
        {"date": "2026-07-18", "transmissions": 2, "tasks_completed": 1}
    ])
    alerts = MagicMock()
    alerts.mappings.return_value.one.return_value = {
        "plans_overdue": 1, "plans_due_30_days": 2, "goals_overdue": 3,
        "goals_without_recent_follow_up": 1, "cancelled_events": 2,
        "events_without_review": 4,
    }
    workload = MagicMock()
    workload.mappings.return_value.__iter__.return_value = iter([
        {"id": "user", "display_name": "Alex", "shift_hours": 35,
         "event_hours": 4, "absence_hours": 0}
    ])
    connection = MagicMock()
    connection.execute.side_effect = [summary, daily, alerts, workload]
    database = MagicMock()
    database.connect.return_value.__enter__.return_value = connection
    with patch("app.routers.pilotage.engine", database), patch(
        "app.routers.pilotage.require_permission"
    ) as permission:
        response = get_indicators(context(), 30)
    permission.assert_called_once_with(context(), "pilotage.read")
    assert response["summary"]["completion_rate"] == 80
    assert response["alerts"]["events_without_review"] == 4
    assert response["workload"][0]["shift_hours"] == 35
    assert response["privacy"] == "aggregated_alerts_scoped_workload"
    assert "content" not in response["daily"][0]
