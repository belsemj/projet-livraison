from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import tournee as crud
from app.schemas.tournee import TourneeRead

router = APIRouter(prefix="/tournees", tags=["tournees"])


@router.get("/", response_model=list[TourneeRead])
def list_tournees(
    id_run: Optional[int] = Query(default=None, description="Filtrer par execution"),
    jour: Optional[date] = Query(default=None, description="Filtrer par date de calcul (YYYY-MM-DD)"),
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
):
    return crud.get_tournees(db, id_run=id_run, jour=jour, skip=skip, limit=limit)


@router.get("/{id_tournee}", response_model=TourneeRead)
def read_tournee(id_tournee: int, db: Session = Depends(get_db)):
    obj = crud.get_tournee(db, id_tournee)
    if obj is None:
        raise HTTPException(status_code=404, detail="Tournee introuvable")
    return obj
