from typing import Optional
from sqlalchemy.orm import Session
from app.models.affectation import Affectation


def get_affectations(db: Session, id_tournee: Optional[int] = None,
                     skip: int = 0, limit: int = 100):
    q = db.query(Affectation)
    if id_tournee is not None:
        q = q.filter(Affectation.id_tournee == id_tournee)
    return q.order_by(Affectation.id_tournee, Affectation.ordre_visite).offset(skip).limit(limit).all()


def get_affectation(db: Session, id_affectation: int):
    return db.query(Affectation).filter(Affectation.id_affectation == id_affectation).first()
