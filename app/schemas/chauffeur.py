from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Statut = Literal["actif", "conge", "maladie"]

# --- Ecart nom API / nom colonne ---------------------------------------------
# Le modele SQLAlchemy Chauffeur stocke le depot de rattachement dans la colonne
# `id_station` (coherent avec la FK vers station.id_station). L'API expose ce
# champ sous le nom metier `id_depot`. On reconcilie par un alias de VALIDATION,
# sans renommer la colonne, sans migrer la base, sans toucher le routeur :
#   - validation_alias="id_station" : a la lecture depuis l'objet ORM
#     (from_attributes), Pydantic remplit id_depot depuis l'attribut id_station.
#   - populate_by_name=True : le champ reste accepte sous son nom `id_depot` en
#     entree (corps de requete POST/PATCH), donc aucune rupture cote clients.
# La sortie JSON conserve le nom `id_depot` (pas de serialization_alias) : le
# contrat de reponse est inchange. Seule la source de lecture est corrigee.


class ChauffeurBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nom: str
    statut: Statut
    id_depot: int = Field(validation_alias="id_station")


class ChauffeurCreate(ChauffeurBase):
    pass


class ChauffeurUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nom: Optional[str] = None
    statut: Optional[Statut] = None
    id_depot: Optional[int] = Field(default=None, validation_alias="id_station")


class ChauffeurRead(ChauffeurBase):
    # from_attributes : lecture depuis l'objet ORM ; id_depot est resolu via
    # validation_alias -> attribut id_station du modele.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_chauffeur: int
