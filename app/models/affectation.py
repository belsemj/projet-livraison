from sqlalchemy import Column, Integer, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Affectation(Base):
    __tablename__ = "affectation"

    id_affectation = Column(Integer, primary_key=True)
    ordre_visite = Column(Integer, nullable=False)
    quantite = Column(Numeric(8, 2), nullable=False)
    id_tournee = Column(Integer, ForeignKey("tournee.id_tournee"), nullable=False)
    id_lot = Column(Integer, ForeignKey("lot.id_lot"), nullable=False)

    __table_args__ = (
        CheckConstraint("ordre_visite > 0", name="chk_aff_ordre"),
        CheckConstraint("quantite > 0", name="chk_aff_qte"),
    )

    tournee = relationship("Tournee", back_populates="affectations")
    lot = relationship("Lot", back_populates="affectations")
