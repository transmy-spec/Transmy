# ruff: noqa: E501
"""Associate supported people with calendar events.

Revision ID: 20260718_0018
Revises: 20260718_0017
Create Date: 2026-07-18
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0018"
down_revision: str | None = "20260718_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE app.schedule_person(
      entry_id uuid NOT NULL REFERENCES app.schedule_entry(id) ON DELETE CASCADE,
      person_id uuid NOT NULL REFERENCES app.supported_person(id),
      added_by uuid NOT NULL REFERENCES app.user_account(id),created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(entry_id,person_id));
      CREATE INDEX ix_schedule_person_person ON app.schedule_person(person_id,entry_id);
      CREATE TABLE app.schedule_plan(
        entry_id uuid NOT NULL REFERENCES app.schedule_entry(id) ON DELETE CASCADE,
        plan_id uuid NOT NULL REFERENCES app.personalized_plan(id),
        linked_by uuid NOT NULL REFERENCES app.user_account(id),created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(entry_id,plan_id));
      CREATE INDEX ix_schedule_plan_plan ON app.schedule_plan(plan_id,entry_id);""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.schedule_plan; DROP TABLE IF EXISTS app.schedule_person")
