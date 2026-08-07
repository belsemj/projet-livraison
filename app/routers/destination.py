from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.destination import DestinationCreate, DestinationUpdate, DestinationRead
from app.crud import destination as crud

router = APIRouter(prefix="/destinations", tags=["destinations"])

INTROUVABLE = {404: {"description": "Destination introuvable"}}


@router.get("/", response_model=list[DestinationRead],
            summary="Lister les destinations")
def lister_destinations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Liste paginee des 100 points de livraison."""
    return crud.list_destinations(db, skip=skip, limit=limit)


@router.get("/{id_destination}", response_model=DestinationRead,
            summary="Lire une destination", responses=INTROUVABLE)
def lire_destination(id_destination: int, db: Session = Depends(get_db)):
    obj = crud.get_destination(db, id_destination)
    if obj is None:
        raise HTTPException(status_code=404, detail="Destination introuvable")
    return obj


@router.post("/", response_model=DestinationRead,
             status_code=status.HTTP_201_CREATED,
             summary="Creer une destination")
def creer_destination(data: DestinationCreate, db: Session = Depends(get_db)):
    """
    Cree un point de livraison.

    Attention : l'ajout d'une destination modifie l'empreinte des noeuds et
    invalide la matrice de distances (voir /distances).
    """
    return crud.create_destination(db, data)


@router.patch("/{id_destination}", response_model=DestinationRead,
              summary="Modifier une destination", responses=INTROUVABLE)
def modifier_destination(id_destination: int, data: DestinationUpdate,
                         db: Session = Depends(get_db)):
    """
    Mise a jour partielle : les champs absents sont laisses inchanges.

    Une modification de latitude ou longitude invalide la matrice de distances.
    """
    obj = crud.update_destination(db, id_destination, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Destination introuvable")
    return obj


@router.delete("/{id_destination}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Supprimer une destination", responses=INTROUVABLE)
def supprimer_destination(id_destination: int, db: Session = Depends(get_db)):
    """
    Suppression physique, sans controle de dependance :
    supprimer une destination portant des lots laisserait des orphelins.
    """
    if not crud.delete_destination(db, id_destination):
        raise HTTPException(status_code=404, detail="Destination introuvable")
    return None
