from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

# Valeurs autorisees, alignees sur les CHECK du modele
Priorite = Literal["haute", "moyenne", "basse"]
Caisson = Literal["standard", "refrigere", "securise"]


class LotBase(BaseModel):
    volume: float = Field(..., gt=0)
    priorite: Priorite = "moyenne"
    fragile: bool = False
    caisson_requis: Caisson = "standard"
    id_destination: int


class LotCreate(LotBase):
    pass


class LotUpdate(BaseModel):
    volume: float | None = Field(None, gt=0)
    priorite: Priorite | None = None
    fragile: bool | None = None
    caisson_requis: Caisson | None = None
    id_destination: int | None = None


class LotRead(LotBase):
    id_lot: int
    model_config = ConfigDict(from_attributes=True)
