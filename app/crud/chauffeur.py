from sqlalchemy.orm import Session
from app.models.chauffeur import Chauffeur
from app.schemas.chauffeur import ChauffeurCreate, ChauffeurUpdate


def get_chauffeurs(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Chauffeur).offset(skip).limit(limit).all()


def get_chauffeur(db: Session, id_chauffeur: int):
    return db.query(Chauffeur).filter(Chauffeur.id_chauffeur == id_chauffeur).first()


def create_chauffeur(db: Session, data: ChauffeurCreate):
    obj = Chauffeur(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_chauffeur(db: Session, id_chauffeur: int, data: ChauffeurUpdate):
    obj = get_chauffeur(db, id_chauffeur)
    if obj is None:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_chauffeur(db: Session, id_chauffeur: int):
    obj = get_chauffeur(db, id_chauffeur)
    if obj is None:
        return None
    db.delete(obj)
    db.commit()
    return obj
