# ruff: noqa: E501
"""Add disabled retention policies and temporary exports.

Revision ID: 20260718_0007
Revises: 20260718_0006
Create Date: 2026-07-18
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0007"
down_revision: str | None = "20260718_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app.permission (code) VALUES
          ('retention.read'), ('retention.manage'), ('export.request'), ('export.download')
        ON CONFLICT (code) DO NOTHING;
        INSERT INTO app.role_permission (role_id, permission_code)
        SELECT '50000000-0000-4000-8000-000000000001', code FROM app.permission
        WHERE code IN ('retention.read','retention.manage','export.request','export.download')
        ON CONFLICT DO NOTHING;
        INSERT INTO app.role_permission (role_id, permission_code)
        SELECT '50000000-0000-4000-8000-000000000004', code FROM app.permission
        WHERE code IN ('retention.read','export.request','export.download')
        ON CONFLICT DO NOTHING;

        CREATE TABLE app.retention_policy (
            data_type text PRIMARY KEY, retention_days integer,
            status text NOT NULL DEFAULT 'pilot_pending'
              CHECK (status IN ('pilot_pending','validated','disabled')),
            purge_enabled boolean NOT NULL DEFAULT false,
            legal_basis text, updated_by uuid REFERENCES app.user_account(id),
            updated_at timestamptz NOT NULL DEFAULT now(), row_version integer NOT NULL DEFAULT 1,
            CHECK (purge_enabled = false OR (status = 'validated' AND retention_days IS NOT NULL))
        );
        INSERT INTO app.retention_policy (data_type) VALUES
          ('person'), ('transmission'), ('task'), ('handover'), ('audit'),
          ('export'), ('session'), ('backup');

        CREATE TABLE app.export_request (
            id uuid PRIMARY KEY, organization_id uuid NOT NULL REFERENCES app.organization(id),
            requested_by uuid NOT NULL REFERENCES app.user_account(id),
            export_type text NOT NULL CHECK (export_type IN ('activity_summary','audit_log')),
            format text NOT NULL CHECK (format IN ('json','csv')),
            reason text NOT NULL, status text NOT NULL DEFAULT 'ready'
              CHECK (status IN ('queued','ready','failed','expired')),
            result_payload jsonb NOT NULL, record_count integer NOT NULL,
            sha256 text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL, downloaded_at timestamptz
        );
        CREATE TABLE app.export_download_ticket (
            id uuid PRIMARY KEY, export_id uuid NOT NULL REFERENCES app.export_request(id),
            token_hash text NOT NULL UNIQUE, created_by uuid NOT NULL REFERENCES app.user_account(id),
            expires_at timestamptz NOT NULL, used_at timestamptz
        );
        CREATE INDEX ix_export_request_actor ON app.export_request(requested_by, created_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.export_download_ticket")
    op.execute("DROP TABLE IF EXISTS app.export_request")
    op.execute("DROP TABLE IF EXISTS app.retention_policy")
