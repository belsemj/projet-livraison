from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Vehicule(Base):
    __tablename__ = "vehicule"

    id_vehicule = Column(Integer, primary_key=True)
    capacite = Column(Numeric(8, 2), nullable=False)
    assurance = Column(Boolean, nullable=False, default=True)
    statut = Column(String(12), nullable=False, default="actif")
    type_caisson = Column(String(15), nullable=False)
    id_station = Column(Integer, ForeignKey("station.id_station"), nullable=False)

    # Binome fixe chauffeur <-> vehicule : un chauffeur attitre par vehicule.
    # unique -> relation 1:1 ; nullable -> reserve / non assure sans chauffeur.
    id_chauffeur = Column(
        Integer,
        ForeignKey("chauffeur.id_chauffeur"),
        unique=True,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("capacite > 0", name="chk_veh_cap"),
        CheckConstraint(
            "statut IN ('actif','reserve','hors_service')", name="chk_veh_statut"
        ),
        CheckConstraint(
            "type_caisson IN ('standard','refrigere','securise')",
            name="chk_veh_caisson",
        ),
    )

    station = relationship("Station", back_populates="vehicules")
    tournees = relationship("Tournee", back_populates="vehicule")
    chauffeur = relationship("Chauffeur", back_populates="vehicule")
