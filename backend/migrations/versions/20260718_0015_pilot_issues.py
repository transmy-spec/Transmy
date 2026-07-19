# ruff: noqa: E501
"""Add pilot issue tracking.

Revision ID: 20260718_0015
Revises: 20260718_0014
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0015"
down_revision: str | None = "20260718_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission(code) VALUES ('pilot_issue.read'),('pilot_issue.manage') ON CONFLICT DO NOTHING;
      INSERT INTO app.role_permission(role_id,permission_code) VALUES
        ('50000000-0000-4000-8000-000000000001','pilot_issue.read'),
        ('50000000-0000-4000-8000-000000000001','pilot_issue.manage'),
        ('50000000-0000-4000-8000-000000000004','pilot_issue.read'),
        ('50000000-0000-4000-8000-000000000004','pilot_issue.manage') ON CONFLICT DO NOTHING;
      CREATE TABLE app.pilot_issue (
        id uuid PRIMARY KEY,organization_id uuid NOT NULL REFERENCES app.organization(id),
        acceptance_code text REFERENCES app.acceptance_scenario(code),
        title text NOT NULL CHECK(length(title) BETWEEN 3 AND 200),
        description text NOT NULL DEFAULT '' CHECK(length(description)<=3000),
        severity text NOT NULL CHECK(severity IN ('minor','major','critical')),
        status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','resolved','accepted')),
        created_by uuid NOT NULL REFERENCES app.user_account(id),assigned_to uuid REFERENCES app.user_account(id),
        resolved_by uuid REFERENCES app.user_account(id),created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),resolved_at timestamptz,row_version integer NOT NULL DEFAULT 1
      );
      CREATE INDEX ix_pilot_issue_status ON app.pilot_issue(organization_id,status,severity);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.pilot_issue")
    op.execute("""DELETE FROM app.role_permission WHERE permission_code LIKE 'pilot_issue.%';
      DELETE FROM app.permission WHERE code LIKE 'pilot_issue.%'""")
