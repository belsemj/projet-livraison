from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60ca2c30a684'
down_revision: Union[str, Sequence[str], None] = '743af3148355'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("vehicule", schema=None) as batch_op:
        batch_op.add_column(sa.Column("id_chauffeur", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint("uq_vehicule_chauffeur", ["id_chauffeur"])
        batch_op.create_foreign_key(
            "fk_vehicule_chauffeur",
            "chauffeur",
            ["id_chauffeur"],
            ["id_chauffeur"],
        )


def downgrade() -> None:
    with op.batch_alter_table("vehicule", schema=None) as batch_op:
        batch_op.drop_constraint("fk_vehicule_chauffeur", type_="foreignkey")
        batch_op.drop_constraint("uq_vehicule_chauffeur", type_="unique")
        batch_op.drop_column("id_chauffeur")
