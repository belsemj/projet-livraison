from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TourneeRead(BaseModel):
    id_tournee: int
    id_run: int
    distance_totale: Optional[float] = None
    statut: str
    date_calcul: datetime
    id_station_depart: int
    id_station_retour: int
    id_chauffeur: int
    id_vehicule: int
    model_config = ConfigDict(from_attributes=True)
