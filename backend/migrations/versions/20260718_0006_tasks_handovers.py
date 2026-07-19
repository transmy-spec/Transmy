# ruff: noqa: E501
"""Add tasks, assignment history and handovers.

Revision ID: 20260718_0006
Revises: 20260718_0005
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0006"
down_revision: str | None = "20260718_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO app.permission (code) VALUES
          ('task.cancel'), ('handover.reopen')
        ON CONFLICT (code) DO NOTHING;
        DELETE FROM app.role_assignment
        WHERE id = '80000000-0000-4000-8000-000000000003';
        INSERT INTO app.role_permission (role_id, permission_code) VALUES
          ('50000000-0000-4000-8000-000000000004', 'task.cancel'),
          ('50000000-0000-4000-8000-000000000004', 'handover.reopen')
        ON CONFLICT DO NOTHING;

        CREATE TABLE app.task (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL REFERENCES app.organization(id),
            unit_id uuid NOT NULL REFERENCES app.unit(id),
            person_id uuid REFERENCES app.supported_person(id),
            transmission_id uuid REFERENCES app.transmission(id),
            title text NOT NULL CHECK (length(title) BETWEEN 2 AND 200),
            description text NOT NULL DEFAULT '',
            status text NOT NULL DEFAULT 'todo'
              CHECK (status IN ('todo', 'in_progress', 'done', 'cancelled')),
            due_at timestamptz NOT NULL,
            priority text NOT NULL DEFAULT 'normal'
              CHECK (priority IN ('normal', 'important', 'urgent')),
            created_by uuid NOT NULL REFERENCES app.user_account(id),
            completed_by uuid REFERENCES app.user_account(id),
            completed_at timestamptz,
            cancellation_reason text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            row_version integer NOT NULL DEFAULT 1
        );
        CREATE TABLE app.task_user_assignment (
            id uuid PRIMARY KEY, task_id uuid NOT NULL REFERENCES app.task(id),
            user_id uuid NOT NULL REFERENCES app.user_account(id),
            assigned_by uuid NOT NULL REFERENCES app.user_account(id),
            assigned_at timestamptz NOT NULL DEFAULT now(), unassigned_at timestamptz
        );
        CREATE UNIQUE INDEX ux_task_user_assignment_active
          ON app.task_user_assignment(task_id) WHERE unassigned_at IS NULL;
        CREATE TABLE app.task_unit_assignment (
            id uuid PRIMARY KEY, task_id uuid NOT NULL REFERENCES app.task(id),
            unit_id uuid NOT NULL REFERENCES app.unit(id),
            assigned_by uuid NOT NULL REFERENCES app.user_account(id),
            assigned_at timestamptz NOT NULL DEFAULT now(), unassigned_at timestamptz
        );
        CREATE UNIQUE INDEX ux_task_unit_assignment_active
          ON app.task_unit_assignment(task_id) WHERE unassigned_at IS NULL;
        CREATE TABLE app.task_event (
            id uuid PRIMARY KEY, task_id uuid NOT NULL REFERENCES app.task(id),
            event_type text NOT NULL, actor_id uuid NOT NULL REFERENCES app.user_account(id),
            occurred_at timestamptz NOT NULL DEFAULT now(), from_state text, to_state text,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX ix_task_unit_due ON app.task(unit_id, status, due_at);

        CREATE TABLE app.handover (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL REFERENCES app.organization(id),
            unit_id uuid NOT NULL REFERENCES app.unit(id),
            period_start timestamptz NOT NULL, period_end timestamptz NOT NULL,
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'closed')),
            created_by uuid NOT NULL REFERENCES app.user_account(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            closed_by uuid REFERENCES app.user_account(id), closed_at timestamptz,
            row_version integer NOT NULL DEFAULT 1,
            CHECK (period_end > period_start)
        );
        CREATE TABLE app.handover_transmission_item (
            id uuid PRIMARY KEY, handover_id uuid NOT NULL REFERENCES app.handover(id),
            transmission_id uuid NOT NULL REFERENCES app.transmission(id), reason text NOT NULL,
            added_by uuid NOT NULL REFERENCES app.user_account(id), added_at timestamptz NOT NULL DEFAULT now(),
            reviewed_by uuid REFERENCES app.user_account(id), reviewed_at timestamptz,
            sort_order integer NOT NULL DEFAULT 0, UNIQUE (handover_id, transmission_id)
        );
        CREATE TABLE app.handover_task_item (
            id uuid PRIMARY KEY, handover_id uuid NOT NULL REFERENCES app.handover(id),
            task_id uuid NOT NULL REFERENCES app.task(id), reason text NOT NULL,
            added_by uuid NOT NULL REFERENCES app.user_account(id), added_at timestamptz NOT NULL DEFAULT now(),
            reviewed_by uuid REFERENCES app.user_account(id), reviewed_at timestamptz,
            sort_order integer NOT NULL DEFAULT 0, UNIQUE (handover_id, task_id)
        );
        CREATE INDEX ix_handover_unit_period ON app.handover(unit_id, period_start DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.handover_task_item")
    op.execute("DROP TABLE IF EXISTS app.handover_transmission_item")
    op.execute("DROP TABLE IF EXISTS app.handover")
    op.execute("DROP TABLE IF EXISTS app.task_event")
    op.execute("DROP TABLE IF EXISTS app.task_unit_assignment")
    op.execute("DROP TABLE IF EXISTS app.task_user_assignment")
    op.execute("DROP TABLE IF EXISTS app.task")
