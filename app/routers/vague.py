"""
Saisie d'une vague de lots (S7).

POST /vagues : persiste un ensemble de lots saisis au formulaire, sous un
id_vague genere, et renvoie cet identifiant. Le front enchaine ensuite avec
POST /optimisations {id_vague} pour lancer le solveur sur cette vague.

SQLite n'applique pas les cles etrangeres par defaut : on verifie ici que
chaque destination et chaque station source existent, avant d'inserer.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.destination import Destination
from app.models.station import Station
from app.crud import vague as crud
from app.schemas.vague import VagueRequete, VagueResultat

router = APIRouter(prefix="/vagues", tags=["vague"])


def _valider_references(db: Session, requete: VagueRequete) -> None:
    """Verifie que destinations et stations referencees existent (une requete
    par ensemble distinct, pas par lot)."""
    dest_demandees = {l.id_destination for l in requete.lots}
    src_demandees = {l.id_station_source for l in requete.lots}

    dest_connues = {
        d for (d,) in db.query(Destination.id_destination)
        .filter(Destination.id_destination.in_(dest_demandees)).all()
    }
    src_connues = {
        s for (s,) in db.query(Station.id_station)
        .filter(Station.id_station.in_(src_demandees)).all()
    }

    dest_inconnues = sorted(dest_demandees - dest_connues)
    src_inconnues = sorted(src_demandees - src_connues)
    if dest_inconnues or src_inconnues:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Reference(s) inexistante(s) dans la base.",
                "destinations_inconnues": dest_inconnues,
                "stations_inconnues": src_inconnues,
            },
        )


@router.post("", response_model=VagueResultat,
             status_code=status.HTTP_201_CREATED,
             summary="Creer une vague de lots")
def creer_vague(requete: VagueRequete, db: Session = Depends(get_db)):
    """
    Persiste les lots saisis sous un nouvel id_vague.

    - 201 : vague creee ; id_vague et id des lots renvoyes.
    - 400 : une destination ou une station source n'existe pas.
    """
    _valider_references(db, requete)

    try:
        id_vague, id_lots = crud.creer_vague(db, requete)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Echec de l'enregistrement de la vague.",
        )

    return VagueResultat(id_vague=id_vague, nb_lots=len(id_lots), id_lots=id_lots)
