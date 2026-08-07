# app/routers/zone.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.clustering import calculer_zones, K_ZONES

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("")
def lire_zones(
    k: int = Query(
        K_ZONES, ge=2, le=20,
        description="Nombre de zones (defaut verrouille = 7).",
    ),
    db: Session = Depends(get_db),
):
    """Renvoie le zonage geographique des destinations (clustering ML).

    Independant de tout run : une destination appartient a sa zone quel que
    soit le run. Distinct de /runs/{id_run}/carte-json (statut servie/
    abandonnee, propre a un run) et de la partition par depot.

    Sortie :
      {
        "k": 7,
        "mapping": {id_destination: id_zone},   # id_zone dans 1..k
        "zones": [{id_zone, n, centre{lat,lon}, destinations[...]}, ...]
      }

    Recalcule a la lecture (rien n'est persiste). 'k' parametrable pour
    exploration ; 7 est la valeur verrouillee (D-serie zonage).
    """
    return calculer_zones(db, k=k)
