# ruff: noqa: E501
"""Add advanced calendar workflows.

Revision ID: 20260719_0020
Revises: 20260718_0019
Create Date: 2026-07-19
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260719_0020"
down_revision: str | None = "20260718_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""INSERT INTO app.permission(code) VALUES ('leave.request'),('leave.approve') ON CONFLICT DO NOTHING;
      INSERT INTO app.role_permission(role_id,permission_code) VALUES
      ('50000000-0000-4000-8000-000000000001','leave.request'),
      ('50000000-0000-4000-8000-000000000001','leave.approve'),
      ('50000000-0000-4000-8000-000000000002','leave.request'),
      ('50000000-0000-4000-8000-000000000003','leave.request'),
      ('50000000-0000-4000-8000-000000000003','leave.approve'),
      ('50000000-0000-4000-8000-000000000004','leave.request'),
      ('50000000-0000-4000-8000-000000000004','leave.approve') ON CONFLICT DO NOTHING;
      ALTER TABLE app.schedule_entry ADD COLUMN approval_status text NOT NULL DEFAULT 'approved'
        CHECK(approval_status IN ('pending','approved','rejected'));
      ALTER TABLE app.schedule_entry ADD COLUMN reviewed_by uuid REFERENCES app.user_account(id);
      ALTER TABLE app.schedule_entry ADD COLUMN reviewed_at timestamptz;
      ALTER TABLE app.schedule_entry ADD COLUMN recurrence_group_id uuid;
      ALTER TABLE app.schedule_participant ADD COLUMN response_status text NOT NULL DEFAULT 'pending'
        CHECK(response_status IN ('pending','accepted','declined'));
      ALTER TABLE app.schedule_participant ADD COLUMN responded_at timestamptz;
      CREATE INDEX ix_schedule_recurrence ON app.schedule_entry(recurrence_group_id) WHERE recurrence_group_id IS NOT NULL;
      CREATE INDEX ix_schedule_approval ON app.schedule_entry(unit_id,approval_status,starts_at) WHERE entry_type='absence';""")


def downgrade() -> None:
    op.execute("""DROP INDEX IF EXISTS app.ix_schedule_approval; DROP INDEX IF EXISTS app.ix_schedule_recurrence;
      ALTER TABLE app.schedule_participant DROP COLUMN IF EXISTS responded_at;
      ALTER TABLE app.schedule_participant DROP COLUMN IF EXISTS response_status;
      ALTER TABLE app.schedule_entry DROP COLUMN IF EXISTS recurrence_group_id;
      ALTER TABLE app.schedule_entry DROP COLUMN IF EXISTS reviewed_at;
      ALTER TABLE app.schedule_entry DROP COLUMN IF EXISTS reviewed_by;
      ALTER TABLE app.schedule_entry DROP COLUMN IF EXISTS approval_status;
      DELETE FROM app.role_permission WHERE permission_code IN ('leave.request','leave.approve');
      DELETE FROM app.permission WHERE code IN ('leave.request','leave.approve');""")
