"""
Schemas de l'endpoint POST /evaluations (Phase 2, S7 J4).

Requete : une affectation MANUELLE figee par l'humain -- la vague concernee et,
par tournee, un couple chauffeur/vehicule avec ses lots imposes.
Reponse : par tournee, l'ordre de visite optimise (TSP) + la performance
(distance, taux de charge) + les violations non bloquantes ; plus un agregat
global et les lots de la vague restes non affectes.

Contrairement a POST /optimisations, l'evaluateur N'ECRIT RIEN en base : il
calcule et renvoie. Pas d'id_run, pas de 201 -- une simple reponse 200.

from_attributes : le modele Violation se construit directement depuis le
dataclass evaluateur.Violation (lecture par attribut), sans conversion
intermediaire -- meme pattern que schemas.optimisation.LotNonServi.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- requete -----------------------------------------------------------------
class AffectationTournee(BaseModel):
    id_chauffeur: int = Field(description="Chauffeur affecte a la tournee.")
    id_vehicule: int = Field(description="Vehicule affecte a la tournee.")
    ids_lots: list[int] = Field(
        description="Lots imposes sur cette tournee. L'ordre est indifferent : "
                    "l'evaluateur recalcule l'ordre de visite (TSP)."
    )


class EvaluationRequete(BaseModel):
    id_vague: str = Field(
        description="Vague dont provient l'affectation. Sert a lister les lots "
                    "de la vague restes non affectes."
    )
    affectations: list[AffectationTournee] = Field(
        min_length=1,
        description="Les tournees imposees. Au moins une.",
    )


# --- reponse -----------------------------------------------------------------
class Violation(BaseModel):
    """Un manquement constate, NON bloquant.

    - capacite : charge de la tournee > capacite du vehicule (id_lot absent,
      c'est un fait de tournee).
    - caisson  : le caisson du vehicule ne couvre pas l'exigence du lot.
    - source   : le lot part d'un depot autre que celui du vehicule.
    """
    model_config = ConfigDict(from_attributes=True)

    type: Literal["capacite", "caisson", "source"]
    message: str
    id_lot: Optional[int] = None


class TourneeEvaluee(BaseModel):
    id_chauffeur: int
    id_vehicule: int
    id_station_depart: int
    # id_lot dans l'ordre de visite optimise ; retour au depot (D34) implicite.
    ordre_lots: list[int]
    distance_km: float
    charge_m3: float
    capacite_m3: float
    taux_charge: float          # charge / capacite, en pourcentage
    violations: list[Violation]


class EvaluationResultat(BaseModel):
    distance_totale_km: float
    nb_tournees: int
    nb_violations: int
    lots_non_affectes: list[int]
    tournees: list[TourneeEvaluee]
