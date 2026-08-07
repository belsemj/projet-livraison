"""ajout de id_station_source et id_vague sur lot

Contrainte de station source (D32, D33). Deux colonnes :

  id_station_source : FK vers station, NULLABLE. Depot ou la marchandise est
      stockee. Donnee d'entree. Nullable car les 120 lots existants n'ont pas
      encore de valeur au moment du ALTER ; le peuplement (script separe) la
      renseigne ensuite. Le passage NOT NULL est reporte a la migration
      PostgreSQL de prod, ou il est trivial. Dette assumee, notee au registre.

  id_vague : VARCHAR(30), NOT NULL, defaut 'vague_0'. Ensemble de commandes a
      optimiser ensemble. Distinct de id_run sur tournee (D32).

SQLite : ajout via batch_alter_table. Un ALTER classique echouerait sur la FK
et sur la contrainte NOT NULL d'une colonne ajoutee a une table peuplee. Le
batch mode reconstruit la table, ce qui contourne les deux limites.

Revision ID: a1b2c3d4e5f6
Revises: 60ca2c30a684
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "60ca2c30a684"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table : indispensable sur SQLite pour ajouter une FK et une
    # colonne NOT NULL avec defaut serveur sur une table deja peuplee.
    with op.batch_alter_table("lot", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("id_station_source", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "id_vague",
                sa.String(length=30),
                nullable=False,
                server_default="vague_0",
            )
        )
        batch_op.create_foreign_key(
            "fk_lot_station_source",
            "station",
            ["id_station_source"],
            ["id_station"],
        )

    # server_default retire apres coup : il a servi a peupler les lignes
    # existantes ; on veut ensuite que la valeur soit fixee explicitement par
    # l'application (defaut cote modele SQLAlchemy), pas par le schema.
    with op.batch_alter_table("lot", schema=None) as batch_op:
        batch_op.alter_column("id_vague", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("lot", schema=None) as batch_op:
        batch_op.drop_constraint("fk_lot_station_source", type_="foreignkey")
        batch_op.drop_column("id_vague")
        batch_op.drop_column("id_station_source")
