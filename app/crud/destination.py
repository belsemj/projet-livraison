from sqlalchemy.orm import Session
from app.models.destination import Destination
from app.schemas.destination import DestinationCreate, DestinationUpdate


def get_destination(db: Session, id_destination: int):
    return db.get(Destination, id_destination)


def list_destinations(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Destination).offset(skip).limit(limit).all()


def create_destination(db: Session, data: DestinationCreate):
    obj = Destination(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_destination(db: Session, id_destination: int, data: DestinationUpdate):
    obj = db.get(Destination, id_destination)
    if obj is None:
        return None
    for champ, valeur in data.model_dump(exclude_unset=True).items():
        setattr(obj, champ, valeur)
    db.commit()
    db.refresh(obj)
    return obj


def delete_destination(db: Session, id_destination: int):
    obj = db.get(Destination, id_destination)
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True
