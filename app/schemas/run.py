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

    Persiste (table lot_non_servi). La destination (id + nom)
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

    Les lots non servis SONT desormais persistes (table lot_non_servi)
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

    nb_lots_non_servis (compte persiste) pour que le selecteur
    signale les runs a abandon.
    """
    id_run: int
    nb_tournees: int
    nb_lots_servis: int
    nb_lots_non_servis: int
    distance_totale_km: float
    date_calcul: datetime


# --- S8 J3 : KPIs (tableau de bord) ------------------------------------------


class KpiTournee(BaseModel):
    """Detail KPI d'une tournee du run (unite volume = m3)."""
    id_tournee: int
    id_vehicule: int
    charge_volume: float      # somme des quantites affectees (m3)
    capacite: float           # capacite du vehicule (m3)
    remplissage_pct: float    # 100 * charge / capacite
    distance_km: float


class KpiDispersion(BaseModel):
    """Dispersion d'une grandeur entre les tournees d'un run (equilibrage).

    ecart_type : ecart-type de population (dispersion sur TOUTES les tournees
    du run, pas un echantillon).
    """
    min: float
    max: float
    moyenne: float
    ecart_type: float


class KpisRun(BaseModel):
    """KPIs d'un run, calcules a la lecture (aucun stockage).

    Composes AU-DESSUS du resume du run (crud_run.lire_run) : distance et
    servis/non servis proviennent du meme fait que l'ecran detail -> pas de
    re-inference, pas de divergence. Les destinations servies / abandonnees
    sont LUES depuis assembler_carte (statut D33-carto), jamais recalculees.
    Seul ajout propre aux KPIs : la capacite -> remplissage + equilibrage.

    Deux comptes de lots servis, volontairement distincts et honnetes :
      - nb_lots_servis          : nombre d'AFFECTATIONS (= ecran detail ; un
                                  lot fractionne compte plusieurs fois),
      - nb_lots_distincts_servis : nombre de lots distincts reellement livres.
    """
    id_run: int
    nb_tournees: int

    # Distance
    distance_totale_km: float

    # Taux d'utilisation (remplissage capacite)
    remplissage_moyen_pct: float

    # Equilibrage de charge (sur volume ET distance)
    equilibrage_volume: KpiDispersion       # m3
    equilibrage_distance: KpiDispersion     # km

    # Servis / non servis
    nb_lots_servis: int
    nb_lots_distincts_servis: int
    nb_lots_non_servis: int
    nb_destinations_servies: int
    nb_destinations_abandonnees: int

    # Detail par tournee
    tournees: list[KpiTournee]
