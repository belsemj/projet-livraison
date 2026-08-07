"""
Consultation des tournees calculees par le solveur (lecture seule).

Aucune ecriture n'est exposee : ces enregistrements sont produits par le
module d'optimisation, jamais saisis manuellement. Conformement au
principe schema vs solveur, l'API se contente de les restituer.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import tournee as crud
from app.schemas.tournee import TourneeRead

router = APIRouter(prefix="/tournees", tags=["tournees"])

INTROUVABLE = {404: {"description": "Tournee introuvable"}}


@router.get("/", response_model=list[TourneeRead],
            summary="Lister les tournees")
def list_tournees(
    id_run: Optional[int] = Query(default=None, description="Filtrer par execution"),
    jour: Optional[date] = Query(default=None,
                                 description="Filtrer par date de calcul (YYYY-MM-DD)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Liste les tournees, filtrable par execution et par date.

    Le filtre `id_run` est l'entree principale : toutes les tournees issues
    d'un meme lancement du solveur partagent cet identifiant, ce qui permet
    de consulter l'historique sans ecraser les resultats anterieurs.

    Renvoie une liste vide tant que le solveur n'a pas ete execute.
    """
    return crud.get_tournees(db, id_run=id_run, jour=jour, skip=skip, limit=limit)


@router.get("/{id_tournee}", response_model=TourneeRead,
            summary="Lire une tournee", responses=INTROUVABLE)
def read_tournee(id_tournee: int, db: Session = Depends(get_db)):
    """Detail d'une tournee : vehicule, station de retour, distance totale."""
    obj = crud.get_tournee(db, id_tournee)
    if obj is None:
        raise HTTPException(status_code=404, detail="Tournee introuvable")
    return obj
