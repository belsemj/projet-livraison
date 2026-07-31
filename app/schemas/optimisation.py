"""
Schemas de l'endpoint POST /optimisations (S6 J1 ; id_vague S7 ; raison S7 J3).

Requete : parametres optionnels de lancement (budget temps + vague ciblee ;
le reste des reglages du solveur est fige par la calibration S5).
Reponse : resume du run, volontairement leger. Le detail imbrique (tournees
+ affectations) releve de GET /runs/{id_run}, cote lecture.

S7 J3 -- canal unifie "lot non servi" : chaque lot non livre porte desormais
une RAISON typee, derivee de l'etat solveur (source unique de verite) au lieu
d'etre soit un 409 bloquant (capacite locale), soit un simple id sans cause.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class LotNonServi(BaseModel):
    """Un lot que le solveur n'a pas livre, avec la cause typee.

    - abandon_solveur : aucun vehicule compatible (caisson absent au depot ou
      mauvaise station source).
    - capacite_locale : des vehicules compatibles existent, mais leur capacite
      cumulee au depot ne suffit pas -> surplus lache.
    - echec_solveur   : le solveur n'a produit aucune solution.

    from_attributes : construit directement depuis le dataclass solveur.LotNonServi
    (lecture par attribut), sans etape de conversion intermediaire.
    """
    model_config = ConfigDict(from_attributes=True)

    id_lot: int
    raison: Literal["abandon_solveur", "capacite_locale", "echec_solveur"]


class OptimisationResultat(BaseModel):
    id_run: int
    statut: str
    distance_totale_km: float
    nb_tournees: int
    nb_lots_servis: int
    nb_lots_non_servis: int
    lots_non_servis: list[LotNonServi]
    avertissements: list[str]
