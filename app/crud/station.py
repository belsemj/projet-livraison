from sqlalchemy.orm import Session
from app.models.station import Station
from app.schemas.station import StationCreate, StationUpdate


def get_station(db: Session, id_station: int):
    return db.get(Station, id_station)


def list_stations(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Station).offset(skip).limit(limit).all()


def create_station(db: Session, data: StationCreate):
    obj = Station(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_station(db: Session, id_station: int, data: StationUpdate):
    obj = db.get(Station, id_station)
    if obj is None:
        return None
    for champ, valeur in data.model_dump(exclude_unset=True).items():
        setattr(obj, champ, valeur)
    db.commit()
    db.refresh(obj)
    return obj


def delete_station(db: Session, id_station: int):
    obj = db.get(Station, id_station)
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True
