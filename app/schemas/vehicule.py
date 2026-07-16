from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

StatutVehicule = Literal["actif", "reserve", "hors_service"]
TypeCaisson = Literal["standard", "refrigere", "securise"]


class VehiculeBase(BaseModel):
    capacite: float = Field(gt=0)
    assurance: bool = True
    statut: StatutVehicule = "actif"
    type_caisson: TypeCaisson
    id_station: int
    id_chauffeur: Optional[int] = None


class VehiculeCreate(VehiculeBase):
    pass


class VehiculeUpdate(BaseModel):
    capacite: Optional[float] = Field(default=None, gt=0)
    assurance: Optional[bool] = None
    statut: Optional[StatutVehicule] = None
    type_caisson: Optional[TypeCaisson] = None
    id_station: Optional[int] = None
    id_chauffeur: Optional[int] = None


class VehiculeRead(VehiculeBase):
    id_vehicule: int
    model_config = ConfigDict(from_attributes=True)
