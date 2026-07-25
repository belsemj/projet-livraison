from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud import run as crud_run
from app.schemas.run import RunLu

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{id_run}", response_model=RunLu)
def lire_run(id_run: int, db: Session = Depends(get_db)):
    """Lit un run et ses tournees imbriquees (arrets ordonnes)."""
    donnees = crud_run.lire_run(db, id_run)
    if donnees is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {id_run} introuvable",
        )
    return donnees
