from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.station import Station
from app.crud import chauffeur as crud
from app.schemas.chauffeur import ChauffeurCreate, ChauffeurUpdate, ChauffeurRead

router = APIRouter(prefix="/chauffeurs", tags=["chauffeurs"])

INTROUVABLE = {404: {"description": "Chauffeur introuvable"}}
DEPOT_INVALIDE = {400: {"description": "Station de rattachement inexistante"}}


def _check_depot(db: Session, id_depot: int):
    if db.query(Station).filter(Station.id_station == id_depot).first() is None:
        raise HTTPException(status_code=400, detail=f"Station (depot) {id_depot} inexistante")


@router.get("/", response_model=list[ChauffeurRead], summary="Lister les chauffeurs")
def list_chauffeurs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Liste paginee des chauffeurs."""
    return crud.get_chauffeurs(db, skip=skip, limit=limit)


@router.get("/{id_chauffeur}", response_model=ChauffeurRead,
            summary="Lire un chauffeur", responses=INTROUVABLE)
def read_chauffeur(id_chauffeur: int, db: Session = Depends(get_db)):
    obj = crud.get_chauffeur(db, id_chauffeur)
    if obj is None:
        raise HTTPException(status_code=404, detail="Chauffeur introuvable")
    return obj


@router.post("/", response_model=ChauffeurRead, status_code=201,
             summary="Creer un chauffeur", responses=DEPOT_INVALIDE)
def create_chauffeur(data: ChauffeurCreate, db: Session = Depends(get_db)):
    """
    Cree un chauffeur rattache a un depot.

    Le binome avec un vehicule ne se declare pas ici mais du cote
    vehicule, via son champ id_chauffeur.
    """
    _check_depot(db, data.id_depot)
    return crud.create_chauffeur(db, data)


@router.patch("/{id_chauffeur}", response_model=ChauffeurRead,
              summary="Modifier un chauffeur",
              responses={**INTROUVABLE, **DEPOT_INVALIDE})
def update_chauffeur(id_chauffeur: int, data: ChauffeurUpdate, db: Session = Depends(get_db)):
    """Mise a jour partielle : les champs absents sont laisses inchanges."""
    if data.id_depot is not None:
        _check_depot(db, data.id_depot)
    obj = crud.update_chauffeur(db, id_chauffeur, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Chauffeur introuvable")
    return obj


@router.delete("/{id_chauffeur}", status_code=204,
               summary="Supprimer un chauffeur", responses=INTROUVABLE)
def delete_chauffeur(id_chauffeur: int, db: Session = Depends(get_db)):
    """
    Suppression physique . Si le chauffeur est en binome,
    le vehicule conserve une reference devenue orpheline.
    """
    obj = crud.delete_chauffeur(db, id_chauffeur)
    if obj is None:
        raise HTTPException(status_code=404, detail="Chauffeur introuvable")
