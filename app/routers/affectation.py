"""
Consultation des affectations lot -> tournee (lecture seule).

Une affectation represente la livraison d'un lot, ou d'une fraction de lot,
par une tournee donnee. Le fractionnement etant autorise, un meme lot peut
apparaitre dans plusieurs affectations.
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import affectation as crud
from app.schemas.affectation import AffectationRead

router = APIRouter(prefix="/affectations", tags=["affectations"])

INTROUVABLE = {404: {"description": "Affectation introuvable"}}


@router.get("/", response_model=list[AffectationRead],
            summary="Lister les affectations")
def list_affectations(
    id_tournee: Optional[int] = Query(default=None, description="Filtrer par tournee"),
    id_run: Optional[int] = Query(default=None,
                                  description="Filtrer par execution du solveur (jointure sur tournee)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Liste les affectations, filtrable par tournee ou par execution du solveur.
    Renvoie une liste vide tant que le solveur n'a pas ete execute.
    """
    return crud.get_affectations(db, id_tournee=id_tournee, id_run=id_run,
                                 skip=skip, limit=limit)


@router.get("/{id_affectation}", response_model=AffectationRead,
            summary="Lire une affectation", responses=INTROUVABLE)
def read_affectation(id_affectation: int, db: Session = Depends(get_db)):
    """Detail d'une affectation : lot concerne, quantite livree, ordre de passage."""
    obj = crud.get_affectation(db, id_affectation)
    if obj is None:
        raise HTTPException(status_code=404, detail="Affectation introuvable")
    return obj
