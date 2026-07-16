from sqlalchemy.orm import Session
from app.models.lot import Lot
from app.schemas.lot import LotCreate, LotUpdate


def get_lot(db: Session, id_lot: int):
    return db.get(Lot, id_lot)


def list_lots(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Lot).offset(skip).limit(limit).all()


def create_lot(db: Session, data: LotCreate):
    obj = Lot(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_lot(db: Session, id_lot: int, data: LotUpdate):
    obj = db.get(Lot, id_lot)
    if obj is None:
        return None
    for champ, valeur in data.model_dump(exclude_unset=True).items():
        setattr(obj, champ, valeur)
    db.commit()
    db.refresh(obj)
    return obj


def delete_lot(db: Session, id_lot: int):
    obj = db.get(Lot, id_lot)
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True
