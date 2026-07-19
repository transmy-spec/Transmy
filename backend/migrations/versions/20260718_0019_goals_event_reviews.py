# ruff: noqa: E501
"""Add encrypted plan goals and event reviews.

Revision ID: 20260718_0019
Revises: 20260718_0018
Create Date: 2026-07-18
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0019"
down_revision: str | None = "20260718_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE app.personalized_goal(
      id uuid PRIMARY KEY,plan_id uuid NOT NULL REFERENCES app.personalized_plan(id),
      status text NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','in_progress','achieved','adapted','abandoned')),
      progress integer NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),target_date date,
      encrypted_payload bytea NOT NULL,created_by uuid NOT NULL REFERENCES app.user_account(id),
      updated_by uuid NOT NULL REFERENCES app.user_account(id),created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),row_version integer NOT NULL DEFAULT 1);
      CREATE INDEX ix_personalized_goal_plan ON app.personalized_goal(plan_id,status,target_date);
      CREATE TABLE app.schedule_review(
      id uuid PRIMARY KEY,entry_id uuid NOT NULL UNIQUE REFERENCES app.schedule_entry(id) ON DELETE CASCADE,
      encrypted_payload bytea NOT NULL,created_by uuid NOT NULL REFERENCES app.user_account(id),
      created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
      row_version integer NOT NULL DEFAULT 1);
      CREATE TABLE app.schedule_attendance(
      review_id uuid NOT NULL REFERENCES app.schedule_review(id) ON DELETE CASCADE,
      person_id uuid NOT NULL REFERENCES app.supported_person(id),attended boolean NOT NULL,
      PRIMARY KEY(review_id,person_id));""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.schedule_attendance; DROP TABLE IF EXISTS app.schedule_review; DROP TABLE IF EXISTS app.personalized_goal")
