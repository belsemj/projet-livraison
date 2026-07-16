from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import affectation as crud
from app.schemas.affectation import AffectationRead

router = APIRouter(prefix="/affectations", tags=["affectations"])


@router.get("/", response_model=list[AffectationRead])
def list_affectations(
    id_tournee: Optional[int] = Query(default=None, description="Filtrer par tournee"),
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
):
    return crud.get_affectations(db, id_tournee=id_tournee, skip=skip, limit=limit)


@router.get("/{id_affectation}", response_model=AffectationRead)
def read_affectation(id_affectation: int, db: Session = Depends(get_db)):
    obj = crud.get_affectation(db, id_affectation)
    if obj is None:
        raise HTTPException(status_code=404, detail="Affectation introuvable")
    return obj
