# ruff: noqa: E501
"""Add encrypted personalized support plans.

Revision ID: 20260718_0016
Revises: 20260718_0015
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0016"
down_revision: str | None = "20260718_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission(code) VALUES ('personalized_plan.read'),('personalized_plan.manage') ON CONFLICT DO NOTHING;
      INSERT INTO app.role_permission(role_id,permission_code)
      SELECT role_id,permission_code FROM (VALUES
        ('50000000-0000-4000-8000-000000000001'::uuid,'personalized_plan.read'),
        ('50000000-0000-4000-8000-000000000001'::uuid,'personalized_plan.manage'),
        ('50000000-0000-4000-8000-000000000002'::uuid,'personalized_plan.read'),
        ('50000000-0000-4000-8000-000000000002'::uuid,'personalized_plan.manage'),
        ('50000000-0000-4000-8000-000000000003'::uuid,'personalized_plan.read'),
        ('50000000-0000-4000-8000-000000000003'::uuid,'personalized_plan.manage'),
        ('50000000-0000-4000-8000-000000000004'::uuid,'personalized_plan.read'),
        ('50000000-0000-4000-8000-000000000004'::uuid,'personalized_plan.manage')
      ) grants(role_id,permission_code) ON CONFLICT DO NOTHING;
      CREATE TABLE app.personalized_plan (
        id uuid PRIMARY KEY,organization_id uuid NOT NULL REFERENCES app.organization(id),
        person_id uuid NOT NULL REFERENCES app.supported_person(id),
        status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','active','closed')),
        review_due_at date,created_by uuid NOT NULL REFERENCES app.user_account(id),
        created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
        row_version integer NOT NULL DEFAULT 1
      );
      CREATE UNIQUE INDEX ux_personalized_plan_current ON app.personalized_plan(person_id) WHERE status IN ('draft','active');
      CREATE TABLE app.personalized_plan_version (
        id uuid PRIMARY KEY,plan_id uuid NOT NULL REFERENCES app.personalized_plan(id),
        version_number integer NOT NULL,encrypted_payload bytea NOT NULL,
        created_by uuid NOT NULL REFERENCES app.user_account(id),created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(plan_id,version_number)
      );
      CREATE INDEX ix_personalized_plan_person ON app.personalized_plan(organization_id,person_id,status);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.personalized_plan_version; DROP TABLE IF EXISTS app.personalized_plan")
    op.execute("""DELETE FROM app.role_permission WHERE permission_code LIKE 'personalized_plan.%';
      DELETE FROM app.permission WHERE code LIKE 'personalized_plan.%'""")
