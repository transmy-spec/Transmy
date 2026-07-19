"""Add optional local HTTP integrations.

Revision ID: 20260718_0012
Revises: 20260718_0011
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0012"
down_revision: str | None = "20260718_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission(code) VALUES ('integration.read'),('integration.manage')
      ON CONFLICT DO NOTHING;
      INSERT INTO app.role_permission(role_id,permission_code) VALUES
        ('50000000-0000-4000-8000-000000000001','integration.read'),
        ('50000000-0000-4000-8000-000000000001','integration.manage')
      ON CONFLICT DO NOTHING;
      CREATE TABLE app.local_integration (
        id uuid PRIMARY KEY,
        organization_id uuid NOT NULL REFERENCES app.organization(id),
        label text NOT NULL CHECK(length(label) BETWEEN 2 AND 100),
        endpoint_url text NOT NULL CHECK(length(endpoint_url) BETWEEN 8 AND 500),
        status text NOT NULL DEFAULT 'disabled' CHECK(status IN ('disabled','enabled')),
        last_tested_at timestamptz,last_test_status text,last_test_message text,
        created_by uuid NOT NULL REFERENCES app.user_account(id),
        created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
        row_version integer NOT NULL DEFAULT 1
      );
      CREATE UNIQUE INDEX ux_local_integration_label
        ON app.local_integration(organization_id,lower(label));
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.local_integration")
    op.execute("""DELETE FROM app.role_permission WHERE permission_code LIKE 'integration.%';
      DELETE FROM app.permission WHERE code LIKE 'integration.%'""")
