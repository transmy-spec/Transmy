"""Add supported people and scoped assignments.

Revision ID: 20260718_0004
Revises: 20260718_0003
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0004"
down_revision: str | None = "20260718_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE app.supported_person (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL REFERENCES app.organization(id),
            internal_reference text NOT NULL,
            family_name text NOT NULL,
            given_name text NOT NULL,
            preferred_name text,
            birth_date date,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
            archived_at timestamptz,
            archived_by uuid REFERENCES app.user_account(id),
            archive_reason text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            row_version integer NOT NULL DEFAULT 1,
            UNIQUE (organization_id, internal_reference),
            CHECK ((status = 'active' AND archived_at IS NULL) OR
                   (status = 'archived' AND archived_at IS NOT NULL))
        );
        CREATE TABLE app.person_assignment (
            id uuid PRIMARY KEY,
            person_id uuid NOT NULL REFERENCES app.supported_person(id),
            unit_id uuid NOT NULL REFERENCES app.unit(id),
            starts_at timestamptz NOT NULL DEFAULT now(),
            ends_at timestamptz,
            is_primary boolean NOT NULL DEFAULT false,
            created_by uuid NOT NULL REFERENCES app.user_account(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            row_version integer NOT NULL DEFAULT 1,
            CHECK (ends_at IS NULL OR ends_at > starts_at)
        );
        CREATE INDEX ix_supported_person_name
          ON app.supported_person (organization_id, family_name, given_name);
        CREATE INDEX ix_person_assignment_active
          ON app.person_assignment (unit_id, person_id) WHERE ends_at IS NULL;
        """
    )
    op.execute(
        """
        INSERT INTO app.permission (code) VALUES
          ('person.archive'), ('person.archive.read'), ('person.history.read'),
          ('task.assign'), ('handover.create'), ('handover.update'), ('handover.close')
        ON CONFLICT (code) DO NOTHING;
        INSERT INTO app.role (id, code, label) VALUES
          ('50000000-0000-4000-8000-000000000003', 'team_manager',
           'Responsable d équipe');
        INSERT INTO app.role_permission (role_id, permission_code)
        SELECT '50000000-0000-4000-8000-000000000003', code FROM app.permission
        WHERE code IN ('organization.read', 'structure.read', 'user.read_minimal',
                       'person.search', 'person.read', 'person.create', 'person.update',
                       'person.archive', 'person.archive.read', 'person.history.read',
                       'transmission.read', 'transmission.create', 'transmission.publish',
                       'acknowledgement.create_self', 'task.read', 'task.create', 'task.update',
                       'task.assign', 'handover.read', 'handover.create', 'handover.update',
                       'handover.close', 'taxonomy.read', 'taxonomy.manage');
        INSERT INTO app.role_assignment (id, user_id, role_id, scope_type, scope_id) VALUES
          ('80000000-0000-4000-8000-000000000003',
           '60000000-0000-4000-8000-000000000002',
           '50000000-0000-4000-8000-000000000003', 'unit',
           '40000000-0000-4000-8000-000000000001');
        """
    )
    op.execute(
        """
        INSERT INTO app.supported_person
          (id, organization_id, internal_reference, family_name, given_name,
           preferred_name, birth_date, status, archived_at, archived_by, archive_reason)
        VALUES
          ('90000000-0000-4000-8000-000000000001',
           '10000000-0000-4000-8000-000000000001', 'HZN-0001', 'Moreau', 'Lina',
           NULL, '1992-04-17', 'active', NULL, NULL, NULL),
          ('90000000-0000-4000-8000-000000000002',
           '10000000-0000-4000-8000-000000000001', 'HZN-0002', 'Diallo', 'Samir',
           'Sam', '1986-11-03', 'active', NULL, NULL, NULL),
          ('90000000-0000-4000-8000-000000000003',
           '10000000-0000-4000-8000-000000000001', 'HZN-0003', 'Martin', 'Louise',
           NULL, '1978-08-29', 'active', NULL, NULL, NULL);
        INSERT INTO app.person_assignment
          (id, person_id, unit_id, is_primary, created_by)
        VALUES
          ('91000000-0000-4000-8000-000000000001',
           '90000000-0000-4000-8000-000000000001',
           '40000000-0000-4000-8000-000000000001', true,
           '60000000-0000-4000-8000-000000000002'),
          ('91000000-0000-4000-8000-000000000002',
           '90000000-0000-4000-8000-000000000002',
           '40000000-0000-4000-8000-000000000001', true,
           '60000000-0000-4000-8000-000000000002'),
          ('91000000-0000-4000-8000-000000000003',
           '90000000-0000-4000-8000-000000000003',
           '40000000-0000-4000-8000-000000000001', true,
           '60000000-0000-4000-8000-000000000002');
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM app.role_assignment WHERE id = '80000000-0000-4000-8000-000000000003'")
    op.execute(
        "DELETE FROM app.role_permission WHERE role_id = '50000000-0000-4000-8000-000000000003'"
    )
    op.execute("DELETE FROM app.role WHERE id = '50000000-0000-4000-8000-000000000003'")
    op.execute("DROP TABLE IF EXISTS app.person_assignment")
    op.execute("DROP TABLE IF EXISTS app.supported_person")
