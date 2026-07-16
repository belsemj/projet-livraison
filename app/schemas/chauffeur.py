from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

Statut = Literal["actif", "conge", "maladie"]


class ChauffeurBase(BaseModel):
    nom: str
    statut: Statut
    id_depot: int


class ChauffeurCreate(ChauffeurBase):
    pass


class ChauffeurUpdate(BaseModel):
    nom: Optional[str] = None
    statut: Optional[Statut] = None
    id_depot: Optional[int] = None


class ChauffeurRead(ChauffeurBase):
    id_chauffeur: int
    model_config = ConfigDict(from_attributes=True)
