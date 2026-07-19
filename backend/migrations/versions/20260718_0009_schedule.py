"""Add team schedules and generic availability.

Revision ID: 20260718_0009
Revises: 20260718_0008
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0009"
down_revision: str | None = "20260718_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission (code) VALUES ('schedule.read'),('schedule.manage')
      ON CONFLICT (code) DO NOTHING;
      INSERT INTO app.role_permission (role_id,permission_code) VALUES
        ('50000000-0000-4000-8000-000000000001','schedule.read'),
        ('50000000-0000-4000-8000-000000000001','schedule.manage'),
        ('50000000-0000-4000-8000-000000000002','schedule.read'),
        ('50000000-0000-4000-8000-000000000004','schedule.read'),
        ('50000000-0000-4000-8000-000000000004','schedule.manage')
      ON CONFLICT DO NOTHING;

      CREATE TABLE app.schedule_entry (
        id uuid PRIMARY KEY,
        organization_id uuid NOT NULL REFERENCES app.organization(id),
        unit_id uuid NOT NULL REFERENCES app.unit(id),
        user_id uuid NOT NULL REFERENCES app.user_account(id),
        entry_type text NOT NULL CHECK (entry_type IN ('shift','absence')),
        starts_at timestamptz NOT NULL,
        ends_at timestamptz NOT NULL,
        label text NOT NULL DEFAULT '' CHECK (length(label)<=120),
        status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','cancelled')),
        created_by uuid NOT NULL REFERENCES app.user_account(id),
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        row_version integer NOT NULL DEFAULT 1,
        CHECK (ends_at>starts_at),
        CHECK (ends_at<=starts_at+interval '7 days')
      );
      CREATE INDEX ix_schedule_unit_period
        ON app.schedule_entry(unit_id,starts_at,ends_at) WHERE status='active';
      CREATE INDEX ix_schedule_user_period
        ON app.schedule_entry(user_id,starts_at,ends_at) WHERE status='active';
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.schedule_entry")
