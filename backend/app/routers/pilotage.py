# ruff: noqa: S608
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from app.database import engine
from app.security import SecurityContext, get_security_context, require_permission

router = APIRouter(prefix="/api/v1/pilotage", tags=["pilotage"])


def _scope() -> str:
    return """EXISTS (SELECT 1 FROM app.membership m
      WHERE m.user_id=:user_id AND m.unit_id=source.unit_id
      AND m.starts_at<=now() AND (m.ends_at IS NULL OR m.ends_at>now()))"""


@router.get("")
def get_indicators(
    context: Annotated[SecurityContext, Depends(get_security_context)],
    days: int = 30,
) -> dict[str, Any]:
    require_permission(context, "pilotage.read")
    if days not in (7, 30, 90):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_period")
    period_end = datetime.combine(date.today() + timedelta(days=1), time.min, UTC)
    period_start = period_end - timedelta(days=days)
    params = {
        "organization_id": context.organization_id,
        "user_id": context.user_id,
        "start": period_start,
        "end": period_end,
        "days": days,
    }
    with engine.connect() as connection:
        summary = dict(connection.execute(text(f"""
          WITH transmissions AS (
            SELECT t.unit_id,t.published_at,i.code AS importance
            FROM app.transmission t JOIN app.importance_level i ON i.id=t.importance_level_id
            WHERE t.organization_id=:organization_id AND t.status='published'
              AND t.published_at>=:start AND t.published_at<:end
          ), tasks AS (
            SELECT t.unit_id,t.status,t.created_at,t.completed_at,t.due_at
            FROM app.task t WHERE t.organization_id=:organization_id
          )
          SELECT
            (SELECT count(*) FROM app.supported_person p WHERE p.organization_id=:organization_id
              AND p.status='active' AND EXISTS (SELECT 1 FROM app.person_assignment pa
                JOIN app.membership m ON m.unit_id=pa.unit_id
                WHERE pa.person_id=p.id AND m.user_id=:user_id AND pa.starts_at<=now()
                AND (pa.ends_at IS NULL OR pa.ends_at>now()) AND m.starts_at<=now()
                AND (m.ends_at IS NULL OR m.ends_at>now()))) AS active_people,
            (SELECT count(*) FROM transmissions source WHERE {_scope()}) AS transmissions,
            (SELECT count(*) FROM transmissions source WHERE {_scope()}
              AND source.importance='urgent') AS urgent_transmissions,
            (SELECT count(*) FROM tasks source WHERE {_scope()}
              AND source.created_at>=:start AND source.created_at<:end) AS tasks_created,
            (SELECT count(*) FROM tasks source WHERE {_scope()}
              AND source.completed_at>=:start AND source.completed_at<:end) AS tasks_completed,
            (SELECT count(*) FROM tasks source WHERE {_scope()}
              AND source.status IN ('todo','in_progress') AND source.due_at<now()) AS tasks_overdue
        """), params).mappings().one())
        daily = [dict(row) for row in connection.execute(text(f"""
          WITH dates AS (
            SELECT generate_series(:start, :end-interval '1 day', interval '1 day') AS day
          ), activity AS (
            SELECT source.published_at AS occurred_at,'transmission' AS kind
            FROM app.transmission source WHERE source.organization_id=:organization_id
              AND source.status='published' AND source.published_at>=:start
              AND source.published_at<:end AND {_scope()}
            UNION ALL
            SELECT source.completed_at,'task' FROM app.task source
            WHERE source.organization_id=:organization_id AND source.completed_at>=:start
              AND source.completed_at<:end AND {_scope()}
          )
          SELECT d.day::date AS date,
            count(*) FILTER (WHERE a.kind='transmission') AS transmissions,
            count(*) FILTER (WHERE a.kind='task') AS tasks_completed
          FROM dates d LEFT JOIN activity a ON a.occurred_at>=d.day
            AND a.occurred_at<d.day+interval '1 day'
          GROUP BY d.day ORDER BY d.day
        """), params).mappings()]
        alerts = dict(connection.execute(text("""
          SELECT
            (SELECT count(DISTINCT pp.id) FROM app.personalized_plan pp
              JOIN app.person_assignment pa ON pa.person_id=pp.person_id
              WHERE pp.organization_id=:organization_id AND pp.status='active'
              AND pp.review_due_at<current_date AND pa.starts_at<=now()
              AND (pa.ends_at IS NULL OR pa.ends_at>now())
              AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
                AND m.unit_id=pa.unit_id AND m.starts_at<=now()
                AND (m.ends_at IS NULL OR m.ends_at>now()))) AS plans_overdue,
            (SELECT count(DISTINCT pp.id) FROM app.personalized_plan pp
              JOIN app.person_assignment pa ON pa.person_id=pp.person_id
              WHERE pp.organization_id=:organization_id AND pp.status='active'
              AND pp.review_due_at BETWEEN current_date AND current_date+30
              AND pa.starts_at<=now() AND (pa.ends_at IS NULL OR pa.ends_at>now())
              AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
                AND m.unit_id=pa.unit_id AND m.starts_at<=now()
                AND (m.ends_at IS NULL OR m.ends_at>now()))) AS plans_due_30_days,
            (SELECT count(DISTINCT g.id) FROM app.personalized_goal g
              JOIN app.personalized_plan pp ON pp.id=g.plan_id
              JOIN app.person_assignment pa ON pa.person_id=pp.person_id
              WHERE pp.organization_id=:organization_id
              AND g.status IN ('planned','in_progress') AND g.target_date<current_date
              AND pa.starts_at<=now() AND (pa.ends_at IS NULL OR pa.ends_at>now())
              AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
                AND m.unit_id=pa.unit_id AND m.starts_at<=now()
                AND (m.ends_at IS NULL OR m.ends_at>now()))) AS goals_overdue,
            (SELECT count(DISTINCT g.id) FROM app.personalized_goal g
              JOIN app.personalized_plan pp ON pp.id=g.plan_id
              JOIN app.person_assignment pa ON pa.person_id=pp.person_id
              WHERE pp.organization_id=:organization_id
              AND g.status IN ('planned','in_progress') AND g.updated_at<now()-interval '30 days'
              AND pa.starts_at<=now() AND (pa.ends_at IS NULL OR pa.ends_at>now())
              AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
                AND m.unit_id=pa.unit_id AND m.starts_at<=now()
                AND (m.ends_at IS NULL OR m.ends_at>now()))) AS goals_without_recent_follow_up,
            (SELECT count(*) FROM app.schedule_entry source
              WHERE source.organization_id=:organization_id AND source.entry_type='event'
              AND source.status='cancelled' AND source.updated_at>=:start
              AND source.updated_at<:end AND EXISTS (SELECT 1 FROM app.membership m
                WHERE m.user_id=:user_id AND m.unit_id=source.unit_id
                AND m.starts_at<=now() AND (m.ends_at IS NULL OR m.ends_at>now())
              )) AS cancelled_events,
            (SELECT count(*) FROM app.schedule_entry source
              WHERE source.organization_id=:organization_id AND source.entry_type='event'
              AND source.status='active' AND source.ends_at<now()
              AND source.ends_at>=now()-interval '30 days'
              AND NOT EXISTS (SELECT 1 FROM app.schedule_review r WHERE r.entry_id=source.id)
              AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
                AND m.unit_id=source.unit_id AND m.starts_at<=now()
                AND (m.ends_at IS NULL OR m.ends_at>now()))) AS events_without_review
        """), params).mappings().one())
        workload = [dict(row) for row in connection.execute(text("""
          SELECT u.id,u.display_name,
            round((COALESCE(sum(EXTRACT(epoch FROM (se.ends_at-se.starts_at)))
              FILTER (WHERE se.entry_type='shift'),0)/3600)::numeric,1) AS shift_hours,
            round((COALESCE(sum(EXTRACT(epoch FROM (se.ends_at-se.starts_at)))
              FILTER (WHERE se.entry_type='event'),0)/3600)::numeric,1) AS event_hours,
            round((COALESCE(sum(EXTRACT(epoch FROM (se.ends_at-se.starts_at)))
              FILTER (WHERE se.entry_type='absence' AND se.approval_status='approved'),0)
              /3600)::numeric,1) AS absence_hours
          FROM app.membership viewer JOIN app.membership member ON member.unit_id=viewer.unit_id
          JOIN app.user_account u ON u.id=member.user_id
          LEFT JOIN app.schedule_entry se ON se.user_id=u.id AND se.unit_id=member.unit_id
            AND se.organization_id=:organization_id AND se.status='active'
            AND se.starts_at<now()+interval '7 days' AND se.ends_at>now()
          WHERE viewer.user_id=:user_id AND u.organization_id=:organization_id
            AND u.status='active' AND viewer.starts_at<=now()
            AND (viewer.ends_at IS NULL OR viewer.ends_at>now())
            AND member.starts_at<=now() AND (member.ends_at IS NULL OR member.ends_at>now())
          GROUP BY u.id,u.display_name ORDER BY u.display_name
        """), params).mappings()]
    created = summary["tasks_created"]
    summary["completion_rate"] = round(summary["tasks_completed"] * 100 / created) if created else 0
    return {
        "period": {"days": days, "start": period_start, "end": period_end},
        "summary": summary,
        "daily": daily,
        "alerts": alerts,
        "workload": workload,
        "privacy": "aggregated_alerts_scoped_workload",
    }
