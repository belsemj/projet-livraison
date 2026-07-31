from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict


class AffectationLue(BaseModel):
    """Un arret dans une tournee. Ids + nom de destination (lisible)."""
    model_config = ConfigDict(from_attributes=True)

    ordre_visite: int
    id_lot: int
    id_destination: int | None
    nom_destination: str | None
    quantite: float


class TourneeLue(BaseModel):
    """Une tournee avec ses arrets ordonnes."""
    model_config = ConfigDict(from_attributes=True)

    id_tournee: int
    id_vehicule: int
    id_chauffeur: int
    id_station_depart: int
    id_station_retour: int
    distance_totale: float | None
    statut: str
    affectations: list[AffectationLue]


class LotNonServiLu(BaseModel):
    """Un lot non livre par le run, avec sa raison et sa destination.

    Persiste (table lot_non_servi) depuis S7 J3. La destination (id + nom)
    alimente le popup carte et le detail sans que le front ait a la resoudre.
    """
    model_config = ConfigDict(from_attributes=True)

    id_lot: int
    raison: Literal["abandon_solveur", "capacite_locale", "echec_solveur"]
    id_destination: int | None
    nom_destination: str | None


class RunLu(BaseModel):
    """Un run reconstruit a partir de ses tournees.

    Il n'existe pas de table 'run' : le resume est recalcule a la lecture.
    'statut' n'est pas un attribut de run (il vit sur chaque tournee).

    S7 J3 : les lots non servis SONT desormais persistes (table lot_non_servi)
    et exposes ici -- meme fait que le resume POST, plus une inference.
    """
    id_run: int
    nb_tournees: int
    nb_lots_servis: int
    nb_lots_non_servis: int
    distance_totale_km: float
    tournees: list[TourneeLue]
    lots_non_servis: list[LotNonServiLu]


class RunResume(BaseModel):
    """Une ligne de la liste des runs (historique).

    Meme socle que RunLu mais sans les tournees imbriquees : juste de quoi
    afficher et selectionner un run. Le resume est recalcule a la lecture,
    'date_calcul' etant le MAX des date_calcul des tournees du run.

    S7 J3 : nb_lots_non_servis (compte persiste) pour que le selecteur
    signale les runs a abandon.
    """
    id_run: int
    nb_tournees: int
    nb_lots_servis: int
    nb_lots_non_servis: int
    distance_totale_km: float
    date_calcul: datetime
