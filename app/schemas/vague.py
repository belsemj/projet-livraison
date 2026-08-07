"""
Schemas de l'endpoint POST /vagues.

Une vague est un ensemble de lots saisis ensemble avant tout calcul. On la
persiste sous un id_vague genere, puis POST /optimisations {id_vague} lance le
solveur sur cette vague uniquement. Ecriture des lots seulement : aucune
optimisation ici (principe schema vs solveur, une seule ecriture par endpoint).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Memes ensembles que les CheckConstraint du modele Lot.
Caisson = Literal["standard", "refrigere", "securise"]
Priorite = Literal["haute", "moyenne", "basse"]


class LotEntree(BaseModel):
    """Un lot saisi au formulaire. volume en m3 (le systeme modelise le
    volume, pas le poids)."""
    volume: float = Field(..., gt=0, description="Volume du lot en m3.")
    caisson_requis: Caisson = "standard"
    id_destination: int = Field(..., description="Point de livraison (base).")
    id_station_source: int = Field(..., description="Depot d'appartenance (base).")
    priorite: Priorite = "moyenne"
    fragile: bool = False


class VagueRequete(BaseModel):
    lots: list[LotEntree] = Field(..., min_length=1,
                                  description="Au moins un lot.")
    id_vague: Optional[str] = Field(
        default=None, max_length=30,
        description="Identifiant impose (optionnel). Sinon genere.",
    )


class VagueResultat(BaseModel):
    id_vague: str
    nb_lots: int
    id_lots: list[int] = Field(..., description="id des lots crees, dans l'ordre.")
