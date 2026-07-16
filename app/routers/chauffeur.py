from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.station import Station
from app.crud import chauffeur as crud
from app.schemas.chauffeur import ChauffeurCreate, ChauffeurUpdate, ChauffeurRead

router = APIRouter(prefix="/chauffeurs", tags=["chauffeurs"])


def _check_depot(db: Session, id_depot: int):
    if db.query(Station).filter(Station.id_station == id_depot).first() is None:
        raise HTTPException(status_code=400, detail=f"Station (depot) {id_depot} inexistante")


@router.get("/", response_model=list[ChauffeurRead])
def list_chauffeurs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_chauffeurs(db, skip=skip, limit=limit)


@router.get("/{id_chauffeur}", response_model=ChauffeurRead)
def read_chauffeur(id_chauffeur: int, db: Session = Depends(get_db)):
    obj = crud.get_chauffeur(db, id_chauffeur)
    if obj is None:
        raise HTTPException(status_code=404, detail="Chauffeur introuvable")
    return obj


@router.post("/", response_model=ChauffeurRead, status_code=201)
def create_chauffeur(data: ChauffeurCreate, db: Session = Depends(get_db)):
    _check_depot(db, data.id_depot)
    return crud.create_chauffeur(db, data)


@router.patch("/{id_chauffeur}", response_model=ChauffeurRead)
def update_chauffeur(id_chauffeur: int, data: ChauffeurUpdate, db: Session = Depends(get_db)):
    if data.id_depot is not None:
        _check_depot(db, data.id_depot)
    obj = crud.update_chauffeur(db, id_chauffeur, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Chauffeur introuvable")
    return obj


@router.delete("/{id_chauffeur}", status_code=204)
def delete_chauffeur(id_chauffeur: int, db: Session = Depends(get_db)):
    obj = crud.delete_chauffeur(db, id_chauffeur)
    if obj is None:
        raise HTTPException(status_code=404, detail="Chauffeur introuvable")
