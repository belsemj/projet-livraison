from typing import Optional
from sqlalchemy.orm import Session
from app.models.affectation import Affectation
from app.models.tournee import Tournee


def get_affectations(db: Session, id_tournee: Optional[int] = None,
                     id_run: Optional[int] = None,
                     skip: int = 0, limit: int = 100):
    """
    Liste les affectations.

    id_tournee filtre directement sur la table affectation.
    id_run porte sur la tournee parente : il exige une jointure,
    id_run n'etant stocke que sur tournee (source unique).
    """
    q = db.query(Affectation)

    if id_run is not None:
        q = q.join(Tournee, Affectation.id_tournee == Tournee.id_tournee)
        q = q.filter(Tournee.id_run == id_run)

    if id_tournee is not None:
        q = q.filter(Affectation.id_tournee == id_tournee)

    return (q.order_by(Affectation.id_tournee, Affectation.ordre_visite)
             .offset(skip).limit(limit).all())


def get_affectation(db: Session, id_affectation: int):
    return db.query(Affectation).filter(
        Affectation.id_affectation == id_affectation).first()
