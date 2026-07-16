from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.station import StationCreate, StationUpdate, StationRead
from app.crud import station as crud

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("/", response_model=list[StationRead])
def lister_stations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return crud.list_stations(db, skip=skip, limit=limit)


@router.get("/{id_station}", response_model=StationRead)
def lire_station(id_station: int, db: Session = Depends(get_db)):
    obj = crud.get_station(db, id_station)
    if obj is None:
        raise HTTPException(status_code=404, detail="Station introuvable")
    return obj


@router.post("/", response_model=StationRead, status_code=status.HTTP_201_CREATED)
def creer_station(data: StationCreate, db: Session = Depends(get_db)):
    return crud.create_station(db, data)


@router.put("/{id_station}", response_model=StationRead)
def modifier_station(id_station: int, data: StationUpdate, db: Session = Depends(get_db)):
    obj = crud.update_station(db, id_station, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Station introuvable")
    return obj


@router.delete("/{id_station}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_station(id_station: int, db: Session = Depends(get_db)):
    if not crud.delete_station(db, id_station):
        raise HTTPException(status_code=404, detail="Station introuvable")
    return None
