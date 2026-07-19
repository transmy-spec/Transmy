"""Fix the seeded organization administrator label.

Revision ID: 20260718_0003
Revises: 20260718_0002
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0003"
down_revision: str | None = "20260718_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE app.role SET label = 'Administrateur de l''organisation' "
        "WHERE code = 'organization_admin'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE app.role SET label = 'Administrateur de l organisation' "
        "WHERE code = 'organization_admin'"
    )
