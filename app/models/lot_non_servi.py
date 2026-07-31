from sqlalchemy import Column, Integer, String, ForeignKey, CheckConstraint, UniqueConstraint
from app.database import Base


class LotNonServi(Base):
    """Un lot qu'un run n'a pas livre, avec la raison (S7 J3).

    Il n'existe pas de table 'run' : id_run vit sur 'tournee' (et ici) comme
    simple identifiant d'execution, sans FK. Cette table enregistre, PAR RUN,
    les lots laisses de cote par le solveur et POURQUOI.

    But : une source unique de verite pour l'abandon. Jusqu'ici le "pourquoi"
    etait soit ephemere (reponse POST), soit re-infere de deux facons
    concurrentes (resume vs carte) -- d'ou la divergence J2. Persiste ici une
    fois, il est relu tel quel par le detail du run et par la carte.

    raison : miroir de solveur.LotNonServi.raison. Contrainte au meme jeu de
    valeurs que le schema (CheckConstraint, comme 'statut' sur tournee).
    """
    __tablename__ = "lot_non_servi"

    id_lot_non_servi = Column(Integer, primary_key=True)
    # Execution ; pas de FK (pas de table 'run'), coherent avec Tournee.id_run.
    id_run = Column(Integer, nullable=False, index=True)
    id_lot = Column(Integer, ForeignKey("lot.id_lot"), nullable=False)
    raison = Column(String(20), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "raison IN ('abandon_solveur','capacite_locale','echec_solveur')",
            name="chk_lns_raison",
        ),
        # Un lot est non servi au plus une fois par run.
        UniqueConstraint("id_run", "id_lot", name="uq_lns_run_lot"),
    )
