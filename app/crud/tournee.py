from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models.tournee import Tournee


def get_tournees(db: Session, id_run: Optional[int] = None,
                 jour: Optional[date] = None, skip: int = 0, limit: int = 100):
    q = db.query(Tournee)
    if id_run is not None:
        q = q.filter(Tournee.id_run == id_run)
    if jour is not None:
        debut = datetime.combine(jour, datetime.min.time())
        fin = debut + timedelta(days=1)
        q = q.filter(Tournee.date_calcul >= debut, Tournee.date_calcul < fin)
    return q.order_by(Tournee.id_tournee).offset(skip).limit(limit).all()


def get_tournee(db: Session, id_tournee: int):
    return db.query(Tournee).filter(Tournee.id_tournee == id_tournee).first()
