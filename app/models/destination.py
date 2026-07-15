from sqlalchemy import Column, Integer, String, Numeric, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Destination(Base):
    __tablename__ = "destination"

    id_destination = Column(Integer, primary_key=True)
    nom = Column(String(80), nullable=False)
    gouvernorat = Column(String(50), nullable=False)
    latitude = Column(Numeric(9, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="chk_dest_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="chk_dest_lon"),
    )

    lots = relationship("Lot", back_populates="destination")
