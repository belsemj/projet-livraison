from pydantic import BaseModel, ConfigDict


class AffectationRead(BaseModel):
    id_affectation: int
    ordre_visite: int
    quantite: float
    id_tournee: int
    id_lot: int
    model_config = ConfigDict(from_attributes=True)
