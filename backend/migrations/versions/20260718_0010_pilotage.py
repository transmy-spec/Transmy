"""Add access to aggregated pilotage indicators.

Revision ID: 20260718_0010
Revises: 20260718_0009
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0010"
down_revision: str | None = "20260718_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission (code) VALUES ('pilotage.read')
      ON CONFLICT (code) DO NOTHING;
      INSERT INTO app.role_permission (role_id,permission_code) VALUES
        ('50000000-0000-4000-8000-000000000001','pilotage.read'),
        ('50000000-0000-4000-8000-000000000004','pilotage.read')
      ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
      DELETE FROM app.role_permission WHERE permission_code='pilotage.read';
      DELETE FROM app.permission WHERE code='pilotage.read';
    """)
