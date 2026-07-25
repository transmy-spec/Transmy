"""Add one-time administrator activation tickets.

Revision ID: 20260725_0021
Revises: 20260719_0020
Create Date: 2026-07-25
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260725_0021"
down_revision: str | None = "20260719_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE app.user_account
          DROP CONSTRAINT user_account_status_check;
        ALTER TABLE app.user_account
          ADD CONSTRAINT user_account_status_check
          CHECK (status IN ('active', 'inactive', 'invited'));

        CREATE TABLE auth_session.account_activation (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL REFERENCES app.user_account(id) ON DELETE CASCADE,
          token_hash text NOT NULL UNIQUE,
          purpose text NOT NULL
            CHECK (purpose IN ('admin_bootstrap', 'admin_reset', 'user_invitation')),
          expires_at timestamptz NOT NULL,
          consumed_at timestamptz,
          revoked_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CHECK (expires_at > created_at),
          CHECK (consumed_at IS NULL OR revoked_at IS NULL)
        );
        CREATE INDEX ix_account_activation_active
          ON auth_session.account_activation(user_id, expires_at)
          WHERE consumed_at IS NULL AND revoked_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS auth_session.account_activation;
        UPDATE app.user_account SET status='inactive' WHERE status='invited';
        ALTER TABLE app.user_account
          DROP CONSTRAINT user_account_status_check;
        ALTER TABLE app.user_account
          ADD CONSTRAINT user_account_status_check
          CHECK (status IN ('active', 'inactive'));
        """
    )
