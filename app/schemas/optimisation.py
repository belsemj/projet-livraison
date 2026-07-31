"""
Schemas de l'endpoint POST /optimisations (S6 J1 ; id_vague S7).

Requete : parametres optionnels de lancement (budget temps + vague ciblee ;
le reste des reglages du solveur est fige par la calibration S5).
Reponse : resume du run, volontairement leger. Le detail imbrique (tournees
+ affectations) releve de GET /runs/{id_run}, cote lecture.
"""

from typing import Optional

from pydantic import BaseModel, Field


class OptimisationRequete(BaseModel):
    limite_secondes: Optional[int] = Field(
        default=None, ge=1, le=120,
        description="Budget de recherche du solveur, en secondes. "
                    "Defaut : 45 (valeur de production recalibree en S6 J1 "
                    "sur le probleme decompose).",
    )
    id_vague: Optional[str] = Field(
        default=None,
        description="Restreint l'optimisation aux lots de cette vague. "
                    "Absent (None) : optimise tous les lots de la base.",
    )


class OptimisationResultat(BaseModel):
    id_run: int
    statut: str
    distance_totale_km: float
    nb_tournees: int
    nb_lots_servis: int
    nb_lots_non_servis: int
    lots_non_servis: list[int]
    avertissements: list[str]
