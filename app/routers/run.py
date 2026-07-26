from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud import run as crud_run
from app.crud.carte import assembler_carte
from app.services.carte_folium import rendre_carte_html
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


@router.get("/{id_run}/carte", response_class=HTMLResponse)
def lire_carte_run(id_run: int, db: Session = Depends(get_db)):
    """Sert une carte Folium (page HTML autonome) du run.

    Option A (S6 J3) : l'API rend la carte, le front l'embarque (iframe).
    La structure produite par assembler_carte() est le socle qui deviendra
    le JSON de l'Option B (Leaflet) plus tard, sans retouche.
    """
    data = assembler_carte(db, id_run)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {id_run} introuvable",
        )
    return HTMLResponse(content=rendre_carte_html(data))
