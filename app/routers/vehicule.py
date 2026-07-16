from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.station import Station
from app.models.chauffeur import Chauffeur
from app.crud import vehicule as crud
from app.schemas.vehicule import VehiculeCreate, VehiculeUpdate, VehiculeRead

router = APIRouter(prefix="/vehicules", tags=["vehicules"])


def _check_station(db: Session, id_station: int):
    if db.query(Station).filter(Station.id_station == id_station).first() is None:
        raise HTTPException(status_code=400, detail=f"Station {id_station} inexistante")


def _check_binome(db: Session, id_chauffeur: int, exclude_id: int | None = None):
    if db.query(Chauffeur).filter(Chauffeur.id_chauffeur == id_chauffeur).first() is None:
        raise HTTPException(status_code=400, detail=f"Chauffeur {id_chauffeur} inexistant")
    if crud.chauffeur_deja_affecte(db, id_chauffeur, exclude_id):
        raise HTTPException(status_code=409, detail=f"Chauffeur {id_chauffeur} deja en binome avec un autre vehicule")


@router.get("/", response_model=list[VehiculeRead])
def list_vehicules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_vehicules(db, skip=skip, limit=limit)


@router.get("/{id_vehicule}", response_model=VehiculeRead)
def read_vehicule(id_vehicule: int, db: Session = Depends(get_db)):
    obj = crud.get_vehicule(db, id_vehicule)
    if obj is None:
        raise HTTPException(status_code=404, detail="Vehicule introuvable")
    return obj


@router.post("/", response_model=VehiculeRead, status_code=201)
def create_vehicule(data: VehiculeCreate, db: Session = Depends(get_db)):
    _check_station(db, data.id_station)
    if data.id_chauffeur is not None:
        _check_binome(db, data.id_chauffeur)
    return crud.create_vehicule(db, data)


@router.patch("/{id_vehicule}", response_model=VehiculeRead)
def update_vehicule(id_vehicule: int, data: VehiculeUpdate, db: Session = Depends(get_db)):
    if data.id_station is not None:
        _check_station(db, data.id_station)
    if data.id_chauffeur is not None:
        _check_binome(db, data.id_chauffeur, exclude_id=id_vehicule)
    obj = crud.update_vehicule(db, id_vehicule, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Vehicule introuvable")
    return obj


@router.delete("/{id_vehicule}", status_code=204)
def delete_vehicule(id_vehicule: int, db: Session = Depends(get_db)):
    obj = crud.delete_vehicule(db, id_vehicule)
    if obj is None:
        raise HTTPException(status_code=404, detail="Vehicule introuvable")
