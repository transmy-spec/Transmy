# ruff: noqa: E501
"""Add pilot readiness register.

Revision ID: 20260718_0013
Revises: 20260718_0012
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0013"
down_revision: str | None = "20260718_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission(code) VALUES ('pilot.read'),('pilot.manage') ON CONFLICT DO NOTHING;
      INSERT INTO app.role_permission(role_id,permission_code) VALUES
        ('50000000-0000-4000-8000-000000000001','pilot.read'),
        ('50000000-0000-4000-8000-000000000001','pilot.manage') ON CONFLICT DO NOTHING;
      CREATE TABLE app.pilot_decision (
        code text PRIMARY KEY,label text NOT NULL,responsible text NOT NULL,
        status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','validated','blocked')),
        evidence text NOT NULL DEFAULT '' CHECK(length(evidence)<=1000),
        updated_by uuid REFERENCES app.user_account(id),updated_at timestamptz,
        row_version integer NOT NULL DEFAULT 1
      );
      INSERT INTO app.pilot_decision(code,label,responsible) VALUES
        ('volume','Volumetrie nominale et pointe','Metier'),
        ('backup','RPO, RTO et cible de sauvegarde','Exploitation'),
        ('retention','Durees et bases legales de conservation','DPO / juridique'),
        ('aipd','Analyse d impact sur la protection des donnees','DPO'),
        ('hosting','Hebergement, localisation et sous-traitants','Securite'),
        ('browsers','Navigateurs et appareils institutionnels','Support'),
        ('independent_audit','Audits independants accessibilite et intrusion','Direction'),
        ('residual_risks','Acceptation des risques residuels','Direction');
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.pilot_decision")
    op.execute("""DELETE FROM app.role_permission WHERE permission_code LIKE 'pilot.%';
      DELETE FROM app.permission WHERE code LIKE 'pilot.%'""")
