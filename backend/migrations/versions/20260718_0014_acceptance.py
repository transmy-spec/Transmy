# ruff: noqa: E501
"""Add pilot business acceptance scenarios.

Revision ID: 20260718_0014
Revises: 20260718_0013
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0014"
down_revision: str | None = "20260718_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO app.permission(code) VALUES ('acceptance.read'),('acceptance.manage') ON CONFLICT DO NOTHING;
      INSERT INTO app.role_permission(role_id,permission_code) VALUES
        ('50000000-0000-4000-8000-000000000001','acceptance.read'),
        ('50000000-0000-4000-8000-000000000001','acceptance.manage'),
        ('50000000-0000-4000-8000-000000000004','acceptance.read'),
        ('50000000-0000-4000-8000-000000000004','acceptance.manage') ON CONFLICT DO NOTHING;
      CREATE TABLE app.acceptance_scenario (
        code text PRIMARY KEY,title text NOT NULL,expected_result text NOT NULL,sort_order integer NOT NULL,
        status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','passed','failed','blocked')),
        notes text NOT NULL DEFAULT '' CHECK(length(notes)<=2000),
        tested_by uuid REFERENCES app.user_account(id),tested_at timestamptz,row_version integer NOT NULL DEFAULT 1
      );
      INSERT INTO app.acceptance_scenario(code,title,expected_result,sort_order) VALUES
        ('login','Connexion et changement de compte','Chaque utilisateur ouvre uniquement sa session individuelle.',1),
        ('scope','Recherche dans le perimetre','Aucune personne hors unite autorisee n est visible.',2),
        ('transmission','Transmission et lecture','Publication, lecture et accuse respectent auteur et destinataires.',3),
        ('task','Tache et echeance','Creation, attribution et cloture sont tracees.',4),
        ('handover','Releve d equipe','Les priorites sont proposees puis la releve est cloturee.',5),
        ('schedule','Planning d equipe','Le chef gere les creneaux sans chevauchement.',6),
        ('attachment','Piece jointe securisee','Le fichier est analyse, telechargeable et audite.',7),
        ('mobile','Usage tablette et mobile','Les parcours essentiels restent utilisables sans chevauchement.',8);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.acceptance_scenario")
    op.execute("""DELETE FROM app.role_permission WHERE permission_code LIKE 'acceptance.%';
      DELETE FROM app.permission WHERE code LIKE 'acceptance.%'""")
