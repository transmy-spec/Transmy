# ruff: noqa: E501
"""Add shared team calendar events.

Revision ID: 20260718_0017
Revises: 20260718_0016
Create Date: 2026-07-18
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0017"
down_revision: str | None = "20260718_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission(code) VALUES ('schedule.event.create') ON CONFLICT DO NOTHING;
      INSERT INTO app.role_permission(role_id,permission_code)
      SELECT id,'schedule.event.create' FROM app.role WHERE code IN
        ('organization_admin','professional','team_manager','service_manager') ON CONFLICT DO NOTHING;
      ALTER TABLE app.schedule_entry DROP CONSTRAINT schedule_entry_entry_type_check;
      ALTER TABLE app.schedule_entry ADD CONSTRAINT schedule_entry_entry_type_check
        CHECK(entry_type IN ('shift','absence','event'));
      CREATE TABLE app.schedule_participant(
        entry_id uuid NOT NULL REFERENCES app.schedule_entry(id) ON DELETE CASCADE,
        user_id uuid NOT NULL REFERENCES app.user_account(id),
        invited_by uuid NOT NULL REFERENCES app.user_account(id),created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(entry_id,user_id)
      );
      CREATE INDEX ix_schedule_participant_user ON app.schedule_participant(user_id,entry_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.schedule_participant")
    op.execute("""DELETE FROM app.role_permission WHERE permission_code='schedule.event.create';
      DELETE FROM app.permission WHERE code='schedule.event.create'""")
