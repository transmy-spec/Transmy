"""Add identity, authorization, sessions, and minimal audit.

Revision ID: 20260718_0002
Revises: 20260718_0001
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0002"
down_revision: str | None = "20260718_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE app.organization (
            id uuid PRIMARY KEY,
            name text NOT NULL,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE app.establishment (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL REFERENCES app.organization(id),
            name text NOT NULL,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive'))
        );
        CREATE TABLE app.service (
            id uuid PRIMARY KEY,
            establishment_id uuid NOT NULL REFERENCES app.establishment(id),
            name text NOT NULL,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive'))
        );
        CREATE TABLE app.unit (
            id uuid PRIMARY KEY,
            service_id uuid NOT NULL REFERENCES app.service(id),
            name text NOT NULL,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive'))
        );
        CREATE TABLE app.user_account (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL REFERENCES app.organization(id),
            issuer text NOT NULL,
            subject text NOT NULL,
            username text NOT NULL,
            display_name text NOT NULL,
            email text,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
            authorization_version integer NOT NULL DEFAULT 1,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (issuer, subject),
            UNIQUE (organization_id, username)
        );
        CREATE TABLE app.role (
            id uuid PRIMARY KEY,
            code text NOT NULL UNIQUE,
            label text NOT NULL
        );
        CREATE TABLE app.permission (
            code text PRIMARY KEY
        );
        CREATE TABLE app.role_permission (
            role_id uuid NOT NULL REFERENCES app.role(id),
            permission_code text NOT NULL REFERENCES app.permission(code),
            PRIMARY KEY (role_id, permission_code)
        );
        CREATE TABLE app.membership (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES app.user_account(id),
            unit_id uuid NOT NULL REFERENCES app.unit(id),
            starts_at timestamptz NOT NULL DEFAULT now(),
            ends_at timestamptz,
            is_primary boolean NOT NULL DEFAULT false
        );
        CREATE TABLE app.role_assignment (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES app.user_account(id),
            role_id uuid NOT NULL REFERENCES app.role(id),
            scope_type text NOT NULL
              CHECK (scope_type IN ('organization', 'establishment', 'unit')),
            scope_id uuid NOT NULL,
            starts_at timestamptz NOT NULL DEFAULT now(),
            ends_at timestamptz
        );
        CREATE TABLE auth_session.login_attempt (
            state_hash char(64) PRIMARY KEY,
            nonce text NOT NULL,
            code_verifier text NOT NULL,
            destination text NOT NULL DEFAULT '/',
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE auth_session.web_session (
            id uuid PRIMARY KEY,
            token_hash char(64) NOT NULL UNIQUE,
            csrf_hash char(64) NOT NULL,
            user_id uuid NOT NULL REFERENCES app.user_account(id),
            authorization_version integer NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL
        );
        CREATE TABLE audit.event (
            id bigserial PRIMARY KEY,
            organization_id uuid REFERENCES app.organization(id),
            actor_user_id uuid REFERENCES app.user_account(id),
            event_type text NOT NULL,
            target_type text,
            target_id uuid,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX ix_web_session_user ON auth_session.web_session(user_id);
        CREATE INDEX ix_audit_event_time ON audit.event(occurred_at DESC);
        """
    )
    op.execute(
        """
        INSERT INTO app.organization (id, name) VALUES
          ('10000000-0000-4000-8000-000000000001', 'Association Horizon');
        INSERT INTO app.establishment (id, organization_id, name) VALUES
          ('20000000-0000-4000-8000-000000000001',
           '10000000-0000-4000-8000-000000000001', 'Maison des Tilleuls');
        """
    )
    op.execute(
        """
        INSERT INTO app.service (id, establishment_id, name) VALUES
          ('30000000-0000-4000-8000-000000000001',
           '20000000-0000-4000-8000-000000000001', 'Accompagnement');
        INSERT INTO app.unit (id, service_id, name) VALUES
          ('40000000-0000-4000-8000-000000000001',
           '30000000-0000-4000-8000-000000000001', 'Unité A');
        INSERT INTO app.role (id, code, label) VALUES
          ('50000000-0000-4000-8000-000000000001', 'organization_admin',
           'Administrateur de l''organisation'),
          ('50000000-0000-4000-8000-000000000002', 'professional', 'Professionnel');
        INSERT INTO app.permission (code) VALUES
          ('organization.read'), ('structure.read'), ('structure.manage'),
          ('user.read_minimal'), ('membership.manage'), ('role.read'), ('role.assign'),
          ('role.manage'),
          ('person.search'), ('person.read'), ('person.create'), ('person.update'),
          ('transmission.read'), ('transmission.create'), ('transmission.publish'),
          ('acknowledgement.create_self'), ('task.read'), ('task.create'), ('task.update'),
          ('handover.read'), ('taxonomy.read'), ('taxonomy.manage'), ('audit.read');
        INSERT INTO app.role_permission (role_id, permission_code)
        SELECT '50000000-0000-4000-8000-000000000001', code FROM app.permission
        WHERE code IN ('organization.read', 'structure.read', 'structure.manage',
                       'user.read_minimal', 'membership.manage', 'role.read', 'role.assign',
                       'role.manage', 'taxonomy.read',
                       'taxonomy.manage', 'audit.read');
        INSERT INTO app.role_permission (role_id, permission_code)
        SELECT '50000000-0000-4000-8000-000000000002', code FROM app.permission
        WHERE code IN ('organization.read', 'structure.read', 'user.read_minimal', 'person.search',
                       'person.read', 'person.create', 'person.update', 'transmission.read',
                       'transmission.create', 'transmission.publish', 'acknowledgement.create_self',
                       'task.read', 'task.create', 'task.update', 'handover.read', 'taxonomy.read');
        """
    )
    op.execute(
        """
        INSERT INTO app.user_account
          (id, organization_id, issuer, subject, username, display_name, email) VALUES
          ('60000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
           'https://localhost/oidc/realms/transmissions', '11111111-1111-4111-8111-111111111111',
           'admin', 'Camille Martin', 'admin@transmissions.test'),
          ('60000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001',
           'https://localhost/oidc/realms/transmissions', '22222222-2222-4222-8222-222222222222',
           'professionnel', 'Alex Bernard', 'professionnel@transmissions.test');
        INSERT INTO app.membership (id, user_id, unit_id, is_primary) VALUES
          ('70000000-0000-4000-8000-000000000001', '60000000-0000-4000-8000-000000000002',
           '40000000-0000-4000-8000-000000000001', true);
        INSERT INTO app.role_assignment (id, user_id, role_id, scope_type, scope_id) VALUES
          ('80000000-0000-4000-8000-000000000001', '60000000-0000-4000-8000-000000000001',
           '50000000-0000-4000-8000-000000000001', 'organization',
           '10000000-0000-4000-8000-000000000001'),
          ('80000000-0000-4000-8000-000000000002', '60000000-0000-4000-8000-000000000002',
           '50000000-0000-4000-8000-000000000002', 'unit', '40000000-0000-4000-8000-000000000001');
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit.event")
    op.execute("DROP TABLE IF EXISTS auth_session.web_session")
    op.execute("DROP TABLE IF EXISTS auth_session.login_attempt")
    op.execute("DROP TABLE IF EXISTS app.role_assignment")
    op.execute("DROP TABLE IF EXISTS app.membership")
    op.execute("DROP TABLE IF EXISTS app.role_permission")
    op.execute("DROP TABLE IF EXISTS app.permission")
    op.execute("DROP TABLE IF EXISTS app.role")
    op.execute("DROP TABLE IF EXISTS app.user_account")
    op.execute("DROP TABLE IF EXISTS app.unit")
    op.execute("DROP TABLE IF EXISTS app.service")
    op.execute("DROP TABLE IF EXISTS app.establishment")
    op.execute("DROP TABLE IF EXISTS app.organization")
