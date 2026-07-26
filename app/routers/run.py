from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud import run as crud_run
from app.crud.carte import assembler_carte
from app.services.carte_folium import rendre_carte_html
from app.schemas.run import RunLu, RunResume

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunResume])
def lister_runs(db: Session = Depends(get_db)):
    """Liste les runs existants (historique), le plus recent d'abord.

    Il n'existe pas de table 'run' : chaque entree est un id_run distinct
    present sur 'tournee', avec un resume recalcule a la lecture. Renvoie une
    liste vide s'il n'y a aucun run. Alimente le futur selecteur de run du front.
    """
    return crud_run.lister_runs(db)


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


@router.get("/{id_run}/carte-json")
def lire_carte_json_run(id_run: int, db: Session = Depends(get_db)):
    """Renvoie la structure geo du run en JSON brut (Option B, Leaflet).

    C'est exactement la structure produite par assembler_carte() — le meme
    socle que la carte Folium (Option A), mais servi tel quel au lieu d'etre
    rendu en HTML. Le front react-leaflet consomme ce JSON et dessine
    lui-meme depots, destinations et tournees.
    """
    data = assembler_carte(db, id_run)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {id_run} introuvable",
        )
    return data
