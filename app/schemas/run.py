from datetime import datetime
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


class RunLu(BaseModel):
    """Un run reconstruit a partir de ses tournees.

    Il n'existe pas de table 'run' : le resume est recalcule a la lecture.
    'statut' et 'lots_non_servis' ne sont pas persistes, donc absents ici.
    """
    id_run: int
    nb_tournees: int
    nb_lots_servis: int
    distance_totale_km: float
    tournees: list[TourneeLue]


class RunResume(BaseModel):
    """Une ligne de la liste des runs (historique).

    Meme socle que RunLu mais sans les tournees imbriquees : juste de quoi
    afficher et selectionner un run. Le resume est recalcule a la lecture,
    'date_calcul' etant le MAX des date_calcul des tournees du run.
    """
    id_run: int
    nb_tournees: int
    nb_lots_servis: int
    distance_totale_km: float
    date_calcul: datetime
