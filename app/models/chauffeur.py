from sqlalchemy import Column, Integer, String, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Chauffeur(Base):
    __tablename__ = "chauffeur"

    id_chauffeur = Column(Integer, primary_key=True)
    nom = Column(String(80), nullable=False)
    statut = Column(String(10), nullable=False, default="actif")
    id_station = Column(Integer, ForeignKey("station.id_station"), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "statut IN ('actif','conge','maladie')", name="chk_chauf_statut"
        ),
    )

    station = relationship("Station", back_populates="chauffeurs")
    tournees = relationship("Tournee", back_populates="chauffeur")
    # Binome fixe (D12) : cote inverse. uselist=False -> un seul vehicule par chauffeur.
    vehicule = relationship("Vehicule", back_populates="chauffeur", uselist=False)
