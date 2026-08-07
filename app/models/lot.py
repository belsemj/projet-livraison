from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Lot(Base):
    __tablename__ = "lot"

    id_lot = Column(Integer, primary_key=True)
    volume = Column(Numeric(8, 2), nullable=False)
    priorite = Column(String(10), nullable=False, default="moyenne")
    fragile = Column(Boolean, nullable=False, default=False)
    caisson_requis = Column(String(15), nullable=False, default="standard")
    id_destination = Column(
        Integer, ForeignKey("destination.id_destination"), nullable=False
    )

    # --- Contrainte de station source ---
    # Depot ou la marchandise est physiquement stockee. Donnee d'ENTREE,
    # pas un resultat de calcul : precede l'optimisation, au meme titre que
    # id_destination. Nullable en dev (SQLite ne fait pas ALTER COLUMN
    # aisement) ; passera NOT NULL a la migration PostgreSQL de prod.
    id_station_source = Column(
        Integer, ForeignKey("station.id_station"), nullable=True
    )
    # Ensemble de commandes a traiter ensemble (une vague). Fige avant tout
    # calcul. A ne pas confondre avec id_run (sur tournee), qui identifie une
    # EXECUTION du solveur : une vague peut donner lieu a plusieurs runs.
    id_vague = Column(String(30), nullable=False, default="vague_0")

    __table_args__ = (
        CheckConstraint("volume > 0", name="chk_lot_vol"),
        CheckConstraint(
            "priorite IN ('haute','moyenne','basse')", name="chk_lot_prio"
        ),
        CheckConstraint(
            "caisson_requis IN ('standard','refrigere','securise')",
            name="chk_lot_caisson",
        ),
    )

    destination = relationship("Destination", back_populates="lots")
    station_source = relationship("Station")
    affectations = relationship("Affectation", back_populates="lot")
