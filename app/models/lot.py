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
    affectations = relationship("Affectation", back_populates="lot")
