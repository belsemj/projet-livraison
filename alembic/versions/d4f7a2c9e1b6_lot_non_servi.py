"""table lot_non_servi (lots abandonnes par run + raison)

Persiste, PAR RUN, les lots que le solveur n'a pas livres et la raison typee
(abandon_solveur / capacite_locale / echec_solveur). Ferme la divergence J2 :
le detail du run et la carte lisent desormais ce meme fait au lieu de le
re-inferer chacun de son cote.

Il n'existe pas de table 'run' : id_run reste un simple entier d'execution
(comme sur 'tournee'), sans FK. FK uniquement sur id_lot -> lot.

SQLite : create_table classique (le batch mode n'est requis que pour ALTER une
table peuplee ; ici on cree une table neuve).

Revision ID: d4f7a2c9e1b6
Revises: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4f7a2c9e1b6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lot_non_servi",
        sa.Column("id_lot_non_servi", sa.Integer(), nullable=False),
        sa.Column("id_run", sa.Integer(), nullable=False),
        sa.Column("id_lot", sa.Integer(), nullable=False),
        sa.Column("raison", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "raison IN ('abandon_solveur','capacite_locale','echec_solveur')",
            name="chk_lns_raison",
        ),
        sa.ForeignKeyConstraint(["id_lot"], ["lot.id_lot"], name="fk_lns_lot"),
        sa.PrimaryKeyConstraint("id_lot_non_servi"),
        sa.UniqueConstraint("id_run", "id_lot", name="uq_lns_run_lot"),
    )
    op.create_index(
        "ix_lot_non_servi_id_run", "lot_non_servi", ["id_run"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_lot_non_servi_id_run", table_name="lot_non_servi")
    op.drop_table("lot_non_servi")
