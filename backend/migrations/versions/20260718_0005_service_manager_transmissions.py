# ruff: noqa: E501
"""Add service manager role and versioned transmissions.

Revision ID: 20260718_0005
Revises: 20260718_0004
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0005"
down_revision: str | None = "20260718_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO app.permission (code) VALUES
          ('transmission.correct'), ('acknowledgement.read_aggregate'),
          ('acknowledgement.read_named')
        ON CONFLICT (code) DO NOTHING;

        DELETE FROM app.role_permission
        WHERE role_id IN ('50000000-0000-4000-8000-000000000002',
                          '50000000-0000-4000-8000-000000000003')
          AND permission_code = 'person.create';

        INSERT INTO app.role (id, code, label) VALUES
          ('50000000-0000-4000-8000-000000000004', 'service_manager', 'Chef de service');
        INSERT INTO app.role_permission (role_id, permission_code)
        SELECT '50000000-0000-4000-8000-000000000004', code FROM app.permission
        WHERE code IN ('organization.read', 'structure.read', 'user.read_minimal',
                       'person.search', 'person.read', 'person.create', 'person.update',
                       'person.archive', 'person.archive.read', 'person.history.read',
                       'transmission.read', 'transmission.create', 'transmission.publish',
                       'transmission.correct', 'acknowledgement.create_self',
                       'acknowledgement.read_aggregate', 'acknowledgement.read_named',
                       'task.read', 'task.create', 'task.update', 'task.assign',
                       'handover.read', 'handover.create', 'handover.update',
                       'handover.close', 'taxonomy.read', 'taxonomy.manage');

        INSERT INTO app.role_permission (role_id, permission_code)
        SELECT '50000000-0000-4000-8000-000000000001', code FROM app.permission
        WHERE code IN ('person.search', 'person.read', 'person.create', 'person.update',
                       'person.archive', 'person.archive.read', 'person.history.read')
        ON CONFLICT DO NOTHING;

        INSERT INTO app.user_account
          (id, organization_id, issuer, subject, username, display_name, email) VALUES
          ('60000000-0000-4000-8000-000000000003',
           '10000000-0000-4000-8000-000000000001',
           'https://localhost/oidc/realms/transmissions',
           '33333333-3333-4333-8333-333333333333', 'chefservice', 'Sophie Laurent',
           'chefservice@transmissions.test');
        INSERT INTO app.membership (id, user_id, unit_id, is_primary) VALUES
          ('70000000-0000-4000-8000-000000000002',
           '60000000-0000-4000-8000-000000000003',
           '40000000-0000-4000-8000-000000000001', true),
          ('70000000-0000-4000-8000-000000000003',
           '60000000-0000-4000-8000-000000000001',
           '40000000-0000-4000-8000-000000000001', true);
        INSERT INTO app.role_assignment (id, user_id, role_id, scope_type, scope_id) VALUES
          ('80000000-0000-4000-8000-000000000004',
           '60000000-0000-4000-8000-000000000003',
           '50000000-0000-4000-8000-000000000004', 'unit',
           '40000000-0000-4000-8000-000000000001');
        """
    )
    op.execute(
        """
        CREATE TABLE app.transmission_category (
            id uuid PRIMARY KEY, organization_id uuid NOT NULL REFERENCES app.organization(id),
            code text NOT NULL, label text NOT NULL, color text NOT NULL,
            sort_order integer NOT NULL DEFAULT 0, status text NOT NULL DEFAULT 'active',
            UNIQUE (organization_id, code)
        );
        CREATE TABLE app.importance_level (
            id uuid PRIMARY KEY, organization_id uuid NOT NULL REFERENCES app.organization(id),
            code text NOT NULL, label text NOT NULL, rank integer NOT NULL,
            requires_acknowledgement boolean NOT NULL DEFAULT false,
            status text NOT NULL DEFAULT 'active', UNIQUE (organization_id, code),
            UNIQUE (organization_id, rank)
        );
        CREATE TABLE app.transmission (
            id uuid PRIMARY KEY, organization_id uuid NOT NULL REFERENCES app.organization(id),
            unit_id uuid NOT NULL REFERENCES app.unit(id),
            person_id uuid NOT NULL REFERENCES app.supported_person(id),
            category_id uuid NOT NULL REFERENCES app.transmission_category(id),
            importance_level_id uuid NOT NULL REFERENCES app.importance_level(id),
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
            author_id uuid NOT NULL REFERENCES app.user_account(id), published_at timestamptz,
            current_version_id uuid, selected_for_handover boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
            row_version integer NOT NULL DEFAULT 1
        );
        CREATE TABLE app.transmission_version (
            id uuid PRIMARY KEY, transmission_id uuid NOT NULL REFERENCES app.transmission(id),
            version_number integer NOT NULL, content text NOT NULL CHECK (length(content) <= 10000),
            change_reason text, created_by uuid NOT NULL REFERENCES app.user_account(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            previous_version_id uuid REFERENCES app.transmission_version(id), content_hash text NOT NULL,
            UNIQUE (transmission_id, version_number)
        );
        ALTER TABLE app.transmission ADD CONSTRAINT fk_transmission_current_version
          FOREIGN KEY (current_version_id) REFERENCES app.transmission_version(id);
        CREATE TABLE app.transmission_acknowledgement (
            id uuid PRIMARY KEY, transmission_id uuid NOT NULL REFERENCES app.transmission(id),
            transmission_version_id uuid NOT NULL REFERENCES app.transmission_version(id),
            user_id uuid NOT NULL REFERENCES app.user_account(id),
            acknowledged_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (transmission_version_id, user_id)
        );
        CREATE INDEX ix_transmission_unit_published ON app.transmission(unit_id, published_at DESC);
        CREATE INDEX ix_transmission_person_published ON app.transmission(person_id, published_at DESC);

        INSERT INTO app.transmission_category (id, organization_id, code, label, color, sort_order) VALUES
          ('a0000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'daily', 'Vie quotidienne', '#29705b', 1),
          ('a0000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001', 'health', 'Sante', '#b14f3f', 2),
          ('a0000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000001', 'activity', 'Activite', '#3d6690', 3);
        INSERT INTO app.importance_level (id, organization_id, code, label, rank, requires_acknowledgement) VALUES
          ('b0000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'normal', 'Normale', 1, false),
          ('b0000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001', 'important', 'Importante', 2, true),
          ('b0000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000001', 'urgent', 'Urgente', 3, true);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.transmission_acknowledgement")
    op.execute(
        "ALTER TABLE app.transmission DROP CONSTRAINT IF EXISTS fk_transmission_current_version"
    )
    op.execute("DROP TABLE IF EXISTS app.transmission_version")
    op.execute("DROP TABLE IF EXISTS app.transmission")
    op.execute("DROP TABLE IF EXISTS app.importance_level")
    op.execute("DROP TABLE IF EXISTS app.transmission_category")
    op.execute("DELETE FROM app.role_assignment WHERE id = '80000000-0000-4000-8000-000000000004'")
    op.execute(
        "DELETE FROM app.membership WHERE id IN ('70000000-0000-4000-8000-000000000002', '70000000-0000-4000-8000-000000000003')"
    )
    op.execute("DELETE FROM app.user_account WHERE id = '60000000-0000-4000-8000-000000000003'")
    op.execute(
        "DELETE FROM app.role_permission WHERE role_id = '50000000-0000-4000-8000-000000000004'"
    )
    op.execute("DELETE FROM app.role WHERE id = '50000000-0000-4000-8000-000000000004'")
