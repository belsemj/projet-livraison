"""
Exposition en lecture seule de la matrice de distances.

Trois usages :
  - /distances/noeuds   : referentiel index <-> entite, indispensable pour
                          interpreter toute sortie du solveur 
  - /distances/{i}/{j}  : verification ponctuelle d'une distance
  - /distances/matrice  : extraction d'un sous-bloc

Aucune ecriture : la matrice geodesique est reconstruite par le service si
son cache est invalide, la matrice routiere ne l'est que par
scripts/build_distances.py.
"""

from typing import Literal

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db          # <-- aligner sur les autres routeurs
from app.services import distances as svc

router = APIRouter(prefix="/distances", tags=["distances"])

Source = Literal["routier", "geodesique"]
MAX_INDICES = 25


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class NoeudOut(BaseModel):
    index: int = Field(..., description="Index canonique 0-104")
    type: str = Field(..., description="'station' ou 'destination'")
    id_entite: int
    nom: str
    latitude: float
    longitude: float


class DistanceOut(BaseModel):
    origine: int
    destination: int
    source: Source
    km: float
    symetrique: bool = Field(
        ..., description="False pour le routier : distance(i,j) != distance(j,i)"
    )


class MatriceOut(BaseModel):
    source: Source
    indices: list[int]
    valeurs: list[list[float]] = Field(
        ..., description="valeurs[a][b] = distance de indices[a] vers indices[b]"
    )
    statut: str = Field(..., description="Etat du cache ayant servi la reponse")


# --------------------------------------------------------------------------
# Acces au service
# --------------------------------------------------------------------------

def _charger(db: Session, source: Source) -> tuple[np.ndarray, list, str]:
    """Renvoie (matrice, noeuds, statut) et traduit les erreurs en HTTP."""
    try:
        if source == "routier":
            return svc.obtenir_matrice_routiere(db)
        matrice, noeuds, motif = svc.obtenir_matrice(db)
        return matrice, noeuds, f"geodesique:{motif}"
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


def _valider_index(i: int, n: int) -> None:
    if not 0 <= i < n:
        raise HTTPException(
            status_code=404,
            detail=f"index {i} hors bornes : attendu entre 0 et {n - 1}",
        )


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@router.get(
    "/noeuds",
    response_model=list[NoeudOut],
    summary="Referentiel des noeuds",
    responses={503: {"description": "Donnees de reference incompletes"}},
)
def lire_noeuds(db: Session = Depends(get_db)):
    """
    Table de correspondance entre l'index de la matrice et l'entite metier.

    Ordre canonique fige : index 0-4 = stations, 5-104 = destinations.
    """
    try:
        noeuds = svc.charger_noeuds(db)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return [
        NoeudOut(index=nd.index, type=nd.type, id_entite=nd.id_entite,
                 nom=nd.nom, latitude=nd.latitude, longitude=nd.longitude)
        for nd in noeuds
    ]


@router.get(
    "/matrice",
    response_model=MatriceOut,
    summary="Sous-bloc de la matrice",
    responses={
        400: {"description": "Parametre indices absent ou trop large"},
        404: {"description": "Index hors bornes"},
        503: {"description": "Matrice indisponible"},
    },
)
def lire_matrice(
    indices: str = Query(
        ...,
        description=f"Indices separes par des virgules, {MAX_INDICES} au maximum. "
                    "Exemple : 0,1,2,5,6",
        examples=["0,1,2,3,4"],
    ),
    source: Source = "routier",
    db: Session = Depends(get_db),
):
    """
    Extrait un sous-bloc carre de la matrice.

    Le parametre `indices` est obligatoire : la matrice complete represente
    11 025 valeurs, illisibles dans une reponse HTTP.
    """
    try:
        liste = [int(x) for x in indices.split(",") if x.strip() != ""]
    except ValueError:
        raise HTTPException(status_code=400, detail="indices : entiers attendus")
    if not liste:
        raise HTTPException(status_code=400, detail="indices : liste vide")
    if len(liste) > MAX_INDICES:
        raise HTTPException(
            status_code=400,
            detail=f"{len(liste)} indices demandes, {MAX_INDICES} au maximum",
        )

    matrice, noeuds, statut = _charger(db, source)
    for i in liste:
        _valider_index(i, len(noeuds))

    bloc = [[round(float(matrice[i, j]), 3) for j in liste] for i in liste]
    return MatriceOut(source=source, indices=liste, valeurs=bloc, statut=statut)


@router.get(
    "/{i}/{j}",
    response_model=DistanceOut,
    summary="Distance entre deux noeuds",
    responses={
        404: {"description": "Index hors bornes"},
        503: {"description": "Matrice indisponible"},
    },
)
def lire_distance(
    i: int,
    j: int,
    source: Source = "routier",
    db: Session = Depends(get_db),
):
    """
    Distance en km du noeud `i` vers le noeud `j`.

    Attention : pour `source=routier` l'ordre est significatif.
    La distance de i vers j peut differer de celle de j vers i.
    """
    matrice, noeuds, _ = _charger(db, source)
    _valider_index(i, len(noeuds))
    _valider_index(j, len(noeuds))
    return DistanceOut(
        origine=i,
        destination=j,
        source=source,
        km=round(float(matrice[i, j]), 3),
        symetrique=(source == "geodesique"),
    )
