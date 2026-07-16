from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.destination import DestinationCreate, DestinationUpdate, DestinationRead
from app.crud import destination as crud

router = APIRouter(prefix="/destinations", tags=["destinations"])


@router.get("/", response_model=list[DestinationRead])
def lister_destinations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return crud.list_destinations(db, skip=skip, limit=limit)


@router.get("/{id_destination}", response_model=DestinationRead)
def lire_destination(id_destination: int, db: Session = Depends(get_db)):
    obj = crud.get_destination(db, id_destination)
    if obj is None:
        raise HTTPException(status_code=404, detail="Destination introuvable")
    return obj


@router.post("/", response_model=DestinationRead, status_code=status.HTTP_201_CREATED)
def creer_destination(data: DestinationCreate, db: Session = Depends(get_db)):
    return crud.create_destination(db, data)


@router.put("/{id_destination}", response_model=DestinationRead)
def modifier_destination(id_destination: int, data: DestinationUpdate, db: Session = Depends(get_db)):
    obj = crud.update_destination(db, id_destination, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Destination introuvable")
    return obj


@router.delete("/{id_destination}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_destination(id_destination: int, db: Session = Depends(get_db)):
    if not crud.delete_destination(db, id_destination):
        raise HTTPException(status_code=404, detail="Destination introuvable")
    return None
