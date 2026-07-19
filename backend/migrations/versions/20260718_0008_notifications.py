"""Add internal notification state.

Revision ID: 20260718_0008
Revises: 20260718_0007
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0008"
down_revision: str | None = "20260718_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app.permission (code) VALUES ('notification.read'), ('notification.manage')
        ON CONFLICT (code) DO NOTHING;
        INSERT INTO app.role_permission (role_id, permission_code)
        SELECT role_id, permission_code FROM (VALUES
          ('50000000-0000-4000-8000-000000000001'::uuid, 'notification.read'),
          ('50000000-0000-4000-8000-000000000001'::uuid, 'notification.manage'),
          ('50000000-0000-4000-8000-000000000002'::uuid, 'notification.read'),
          ('50000000-0000-4000-8000-000000000002'::uuid, 'notification.manage'),
          ('50000000-0000-4000-8000-000000000004'::uuid, 'notification.read'),
          ('50000000-0000-4000-8000-000000000004'::uuid, 'notification.manage')
        ) AS grants(role_id, permission_code)
        ON CONFLICT DO NOTHING;

        CREATE TABLE app.notification_state (
          user_id uuid NOT NULL REFERENCES app.user_account(id),
          notification_key text NOT NULL CHECK (length(notification_key) BETWEEN 3 AND 200),
          read_at timestamptz, dismissed_at timestamptz,
          updated_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, notification_key)
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.notification_state")
