from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Tournee(Base):
    __tablename__ = "tournee"

    id_tournee = Column(Integer, primary_key=True)
    id_run = Column(Integer, nullable=False)  # identifiant de l'execution (historique)
    distance_totale = Column(Numeric(10, 2))
    statut = Column(String(12), nullable=False, default="planifiee")
    date_calcul = Column(DateTime, nullable=False, server_default=func.now())
    id_station_depart = Column(Integer, ForeignKey("station.id_station"), nullable=False)
    id_station_retour = Column(Integer, ForeignKey("station.id_station"), nullable=False)
    id_chauffeur = Column(Integer, ForeignKey("chauffeur.id_chauffeur"), nullable=False)
    id_vehicule = Column(Integer, ForeignKey("vehicule.id_vehicule"), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "statut IN ('planifiee','en_cours','terminee')", name="chk_tour_statut"
        ),
    )

    station_depart = relationship(
        "Station", foreign_keys=[id_station_depart]
    )
    station_retour = relationship(
        "Station", foreign_keys=[id_station_retour]
    )
    chauffeur = relationship("Chauffeur", back_populates="tournees")
    vehicule = relationship("Vehicule", back_populates="tournees")
    affectations = relationship("Affectation", back_populates="tournee")
