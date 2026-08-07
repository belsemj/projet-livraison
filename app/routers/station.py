from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.station import StationCreate, StationUpdate, StationRead
from app.crud import station as crud

router = APIRouter(prefix="/stations", tags=["stations"])

INTROUVABLE = {404: {"description": "Station introuvable"}}


@router.get("/", response_model=list[StationRead], summary="Lister les stations")
def lister_stations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Liste paginee des 5 depots regionaux."""
    return crud.list_stations(db, skip=skip, limit=limit)


@router.get("/{id_station}", response_model=StationRead,
            summary="Lire une station", responses=INTROUVABLE)
def lire_station(id_station: int, db: Session = Depends(get_db)):
    obj = crud.get_station(db, id_station)
    if obj is None:
        raise HTTPException(status_code=404, detail="Station introuvable")
    return obj


@router.post("/", response_model=StationRead, status_code=status.HTTP_201_CREATED,
             summary="Creer une station")
def creer_station(data: StationCreate, db: Session = Depends(get_db)):
    """
    Cree un depot.

    Attention : l'ajout ou le retrait d'une station modifie l'empreinte des
    noeuds et invalide la matrice de distances (voir /distances).
    """
    return crud.create_station(db, data)


@router.patch("/{id_station}", response_model=StationRead,
              summary="Modifier une station", responses=INTROUVABLE)
def modifier_station(id_station: int, data: StationUpdate, db: Session = Depends(get_db)):
    """
    Mise a jour partielle : les champs absents du corps de la requete sont
    laisses inchanges.

    Une modification de latitude ou longitude invalide la matrice de distances
    (voir /distances).
    """
    obj = crud.update_station(db, id_station, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Station introuvable")
    return obj


@router.delete("/{id_station}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Supprimer une station", responses=INTROUVABLE)
def supprimer_station(id_station: int, db: Session = Depends(get_db)):
    """
    Suppression physique, sans controle de dependance :
    supprimer une station referencee par des chauffeurs ou des vehicules
    laisserait des enregistrements orphelins.
    """
    if not crud.delete_station(db, id_station):
        raise HTTPException(status_code=404, detail="Station introuvable")
    return None
