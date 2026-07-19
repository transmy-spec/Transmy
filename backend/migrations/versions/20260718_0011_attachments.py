"""Add scanned transmission attachments.

Revision ID: 20260718_0011
Revises: 20260718_0010
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0011"
down_revision: str | None = "20260718_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission (code) VALUES
        ('attachment.read'),('attachment.create'),('attachment.delete_draft')
      ON CONFLICT (code) DO NOTHING;
      INSERT INTO app.role_permission (role_id,permission_code)
      SELECT role_id,permission_code FROM (VALUES
        ('50000000-0000-4000-8000-000000000001'::uuid),
        ('50000000-0000-4000-8000-000000000002'::uuid),
        ('50000000-0000-4000-8000-000000000004'::uuid)
      ) roles(role_id) CROSS JOIN (VALUES
        ('attachment.read'),('attachment.create'),('attachment.delete_draft')
      ) permissions(permission_code) ON CONFLICT DO NOTHING;

      CREATE TABLE app.transmission_attachment (
        id uuid PRIMARY KEY,
        organization_id uuid NOT NULL REFERENCES app.organization(id),
        transmission_id uuid NOT NULL REFERENCES app.transmission(id),
        uploaded_by uuid NOT NULL REFERENCES app.user_account(id),
        original_name text NOT NULL CHECK (length(original_name) BETWEEN 1 AND 180),
        media_type text NOT NULL CHECK (media_type IN ('application/pdf','image/jpeg','image/png')),
        byte_size integer NOT NULL CHECK (byte_size BETWEEN 1 AND 5242880),
        sha256 char(64) NOT NULL,
        scan_status text NOT NULL CHECK (scan_status='clean'),
        content bytea NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE INDEX ix_attachment_transmission
        ON app.transmission_attachment(transmission_id,created_at);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.transmission_attachment")
    op.execute("""DELETE FROM app.role_permission WHERE permission_code LIKE 'attachment.%';
      DELETE FROM app.permission WHERE code LIKE 'attachment.%'""")
