from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.lot import LotCreate, LotUpdate, LotRead
from app.crud import lot as crud
from app.crud import destination as crud_dest

router = APIRouter(prefix="/lots", tags=["lots"])


def _verifier_destination(db: Session, id_destination: int):
    # SQLite n'applique pas les FK par defaut : on controle ici
    if crud_dest.get_destination(db, id_destination) is None:
        raise HTTPException(status_code=400, detail=f"Destination {id_destination} introuvable")


@router.get("/", response_model=list[LotRead])
def lister_lots(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return crud.list_lots(db, skip=skip, limit=limit)


@router.get("/{id_lot}", response_model=LotRead)
def lire_lot(id_lot: int, db: Session = Depends(get_db)):
    obj = crud.get_lot(db, id_lot)
    if obj is None:
        raise HTTPException(status_code=404, detail="Lot introuvable")
    return obj


@router.post("/", response_model=LotRead, status_code=status.HTTP_201_CREATED)
def creer_lot(data: LotCreate, db: Session = Depends(get_db)):
    _verifier_destination(db, data.id_destination)
    return crud.create_lot(db, data)


@router.put("/{id_lot}", response_model=LotRead)
def modifier_lot(id_lot: int, data: LotUpdate, db: Session = Depends(get_db)):
    if data.id_destination is not None:
        _verifier_destination(db, data.id_destination)
    obj = crud.update_lot(db, id_lot, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Lot introuvable")
    return obj


@router.delete("/{id_lot}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_lot(id_lot: int, db: Session = Depends(get_db)):
    if not crud.delete_lot(db, id_lot):
        raise HTTPException(status_code=404, detail="Lot introuvable")
    return None
