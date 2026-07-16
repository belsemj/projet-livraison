from sqlalchemy.orm import Session
from app.models.vehicule import Vehicule
from app.schemas.vehicule import VehiculeCreate, VehiculeUpdate


def get_vehicules(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Vehicule).offset(skip).limit(limit).all()


def get_vehicule(db: Session, id_vehicule: int):
    return db.query(Vehicule).filter(Vehicule.id_vehicule == id_vehicule).first()


def chauffeur_deja_affecte(db: Session, id_chauffeur: int, exclude_id: int | None = None):
    q = db.query(Vehicule).filter(Vehicule.id_chauffeur == id_chauffeur)
    if exclude_id is not None:
        q = q.filter(Vehicule.id_vehicule != exclude_id)
    return q.first() is not None


def create_vehicule(db: Session, data: VehiculeCreate):
    obj = Vehicule(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_vehicule(db: Session, id_vehicule: int, data: VehiculeUpdate):
    obj = get_vehicule(db, id_vehicule)
    if obj is None:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_vehicule(db: Session, id_vehicule: int):
    obj = get_vehicule(db, id_vehicule)
    if obj is None:
        return None
    db.delete(obj)
    db.commit()
    return obj
