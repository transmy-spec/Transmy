"""Align seeded accounts with the configured OIDC issuer.

Revision ID: 20260801_0021
Revises: 20260719_0020
"""

from alembic import op
from sqlalchemy import bindparam, text

from app.config import get_settings

revision: str = "20260801_0021"
down_revision: str | None = "20260719_0020"
branch_labels: str | None = None
depends_on: str | None = None

_LOCAL_ISSUER = "https://localhost/oidc/realms/transmissions"
_SEEDED_ACCOUNT_IDS = (
    "60000000-0000-4000-8000-000000000001",
    "60000000-0000-4000-8000-000000000002",
    "60000000-0000-4000-8000-000000000003",
)


def _configured_issuer() -> str:
    return get_settings().oidc_issuer


def _update_seeded_issuer(current_issuer: str, replacement_issuer: str) -> None:
    statement = text(
        """
        UPDATE app.user_account
        SET issuer = :replacement_issuer
        WHERE issuer = :current_issuer
          AND id::text IN :seeded_account_ids
        """
    ).bindparams(bindparam("seeded_account_ids", expanding=True))
    op.get_bind().execute(
        statement,
        {
            "current_issuer": current_issuer,
            "replacement_issuer": replacement_issuer,
            "seeded_account_ids": _SEEDED_ACCOUNT_IDS,
        },
    )


def upgrade() -> None:
    _update_seeded_issuer(_LOCAL_ISSUER, _configured_issuer())


def downgrade() -> None:
    # Keep the corrected issuer: reverting data would break authentication
    # for non-local deployments running the preceding application revision.
    pass
