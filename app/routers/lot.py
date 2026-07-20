from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.lot import LotCreate, LotUpdate, LotRead
from app.crud import lot as crud
from app.crud import destination as crud_dest

router = APIRouter(prefix="/lots", tags=["lots"])

INTROUVABLE = {404: {"description": "Lot introuvable"}}
DEST_INVALIDE = {400: {"description": "Destination referencee inexistante"}}


def _verifier_destination(db: Session, id_destination: int):
    # SQLite n'applique pas les FK par defaut : on controle ici
    if crud_dest.get_destination(db, id_destination) is None:
        raise HTTPException(status_code=400, detail=f"Destination {id_destination} introuvable")


@router.get("/", response_model=list[LotRead], summary="Lister les lots")
def lister_lots(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Liste paginee des lots a livrer."""
    return crud.list_lots(db, skip=skip, limit=limit)


@router.get("/{id_lot}", response_model=LotRead,
            summary="Lire un lot", responses=INTROUVABLE)
def lire_lot(id_lot: int, db: Session = Depends(get_db)):
    obj = crud.get_lot(db, id_lot)
    if obj is None:
        raise HTTPException(status_code=404, detail="Lot introuvable")
    return obj


@router.post("/", response_model=LotRead, status_code=status.HTTP_201_CREATED,
             summary="Creer un lot", responses=DEST_INVALIDE)
def creer_lot(data: LotCreate, db: Session = Depends(get_db)):
    """
    Cree un lot rattache a une destination.

    Les contraintes metier (volume, fragilite, caisson requis, fractionnement)
    ne sont pas verifiees ici : elles relevent du solveur, conformement au
    principe schema vs solveur.
    """
    _verifier_destination(db, data.id_destination)
    return crud.create_lot(db, data)


@router.patch("/{id_lot}", response_model=LotRead,
              summary="Modifier un lot",
              responses={**INTROUVABLE, **DEST_INVALIDE})
def modifier_lot(id_lot: int, data: LotUpdate, db: Session = Depends(get_db)):
    """Mise a jour partielle : les champs absents sont laisses inchanges."""
    if data.id_destination is not None:
        _verifier_destination(db, data.id_destination)
    obj = crud.update_lot(db, id_lot, data)
    if obj is None:
        raise HTTPException(status_code=404, detail="Lot introuvable")
    return obj


@router.delete("/{id_lot}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Supprimer un lot", responses=INTROUVABLE)
def supprimer_lot(id_lot: int, db: Session = Depends(get_db)):
    """Suppression physique (question ouverte Q7)."""
    if not crud.delete_lot(db, id_lot):
        raise HTTPException(status_code=404, detail="Lot introuvable")
    return None
