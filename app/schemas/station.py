from pydantic import BaseModel, ConfigDict, Field


class StationBase(BaseModel):
    nom: str = Field(..., max_length=80)
    gouvernorat: str = Field(..., max_length=50)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class StationCreate(StationBase):
    pass


class StationUpdate(BaseModel):
    # tous optionnels : autorise une mise a jour partielle (PUT)
    nom: str | None = Field(None, max_length=80)
    gouvernorat: str | None = Field(None, max_length=50)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)


class StationRead(StationBase):
    id_station: int
    model_config = ConfigDict(from_attributes=True)  # lit un objet SQLAlchemy
