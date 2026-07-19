"""
Construction de la matrice de distances geodesiques (BF2).

Ordre canonique des noeuds :
    index 0 .. 4    -> stations (depots), id_station croissant
    index 5 .. 104  -> destinations, id_destination croissant

Cette convention d'index est partagee avec le solveur OR-Tools (S5)
et ne doit plus etre modifiee une fois la matrice generee.

D13 : la matrice stockee reste brute (distances geodesiques exactes).
Le plancher applique aux noeuds geographiquement confondus est une regle
metier, portee par matrice_pour_solveur() et non par le stockage.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from geopy.distance import geodesic

from app.models.station import Station
from app.models.destination import Destination

NB_STATIONS = 5
DOSSIER_DONNEES = Path("data")

# Course intra-urbaine moyenne : hypothese de travail, a reviser des que
# les coordonnees GPS reelles des depots seront connues (question Q1).
DISTANCE_PLANCHER_KM = 3.0


@dataclass(frozen=True)
class Noeud:
    index: int
    type: str          # 'station' ou 'destination'
    id_entite: int
    nom: str
    latitude: float
    longitude: float


def charger_noeuds(db) -> list[Noeud]:
    """Lit stations puis destinations dans l'ordre canonique."""
    stations = db.query(Station).order_by(Station.id_station).all()
    destinations = db.query(Destination).order_by(Destination.id_destination).all()

    if len(stations) != NB_STATIONS:
        raise ValueError(f"{len(stations)} stations en base, {NB_STATIONS} attendues")

    noeuds: list[Noeud] = []
    for i, s in enumerate(stations):
        noeuds.append(Noeud(i, "station", s.id_station, s.nom,
                            float(s.latitude), float(s.longitude)))
    for j, d in enumerate(destinations):
        noeuds.append(Noeud(NB_STATIONS + j, "destination", d.id_destination, d.nom,
                            float(d.latitude), float(d.longitude)))
    return noeuds


def entite_vers_index(type_entite: str, id_entite: int) -> int:
    """('station', 4) -> 3   |   ('destination', 1) -> 5"""
    if type_entite == "station":
        return id_entite - 1
    if type_entite == "destination":
        return NB_STATIONS + id_entite - 1
    raise ValueError(f"type inconnu : {type_entite}")


def index_vers_entite(index: int) -> tuple[str, int]:
    """3 -> ('station', 4)   |   5 -> ('destination', 1)"""
    if index < NB_STATIONS:
        return ("station", index + 1)
    return ("destination", index - NB_STATIONS + 1)


def construire_matrice(noeuds: list[Noeud], decimales: int = 3) -> np.ndarray:
    """Matrice carree symetrique des distances geodesiques, en km."""
    n = len(noeuds)
    coords = [(nd.latitude, nd.longitude) for nd in noeuds]
    matrice = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            d = round(geodesic(coords[i], coords[j]).kilometers, decimales)
            matrice[i, j] = d
            matrice[j, i] = d
    return matrice


def matrice_pour_solveur(matrice: np.ndarray,
                         plancher_km: float = DISTANCE_PLANCHER_KM) -> np.ndarray:
    """
    Applique un plancher (D13) aux paires de noeuds distincts mais
    geographiquement confondus : un depot situe au chef-lieu d'une
    destination livrable produit une distance nulle que le solveur
    interpreterait comme une livraison gratuite.

    La matrice d'origine n'est pas modifiee.
    """
    ajustee = matrice.copy()
    n = ajustee.shape[0]
    hors_diag = ~np.eye(n, dtype=bool)
    ajustee[(ajustee == 0) & hors_diag] = plancher_km
    return ajustee


def controler(matrice: np.ndarray, noeuds: list[Noeud]) -> list[str]:
    """Renvoie la liste des anomalies detectees (liste vide = matrice saine)."""
    anomalies: list[str] = []
    n = len(noeuds)
    if matrice.shape != (n, n):
        anomalies.append(f"dimension {matrice.shape}, attendue ({n}, {n})")
    if not np.allclose(np.diag(matrice), 0):
        anomalies.append("diagonale non nulle")
    if not np.allclose(matrice, matrice.T):
        anomalies.append("matrice non symetrique")
    hors_diag = ~np.eye(n, dtype=bool)
    zeros = np.argwhere((matrice == 0) & hors_diag)
    for i, j in zeros:
        if i < j:
            anomalies.append(
                f"distance nulle entre {noeuds[i].nom} (index {i}) et "
                f"{noeuds[j].nom} (index {j}) : coordonnees identiques"
            )
    return anomalies


def sauvegarder(matrice: np.ndarray, noeuds: list[Noeud],
                dossier: Path = DOSSIER_DONNEES) -> None:
    """Ecrit la matrice (.npy et .csv) et le referentiel des noeuds (.csv)."""
    dossier.mkdir(exist_ok=True)
    np.save(dossier / "matrice_geodesique.npy", matrice)

    lignes = ["index,type,id_entite,nom,latitude,longitude"]
    for nd in noeuds:
        nom = nd.nom.replace(",", " ")
        lignes.append(f"{nd.index},{nd.type},{nd.id_entite},{nom},"
                      f"{nd.latitude},{nd.longitude}")
    (dossier / "noeuds.csv").write_text("\n".join(lignes), encoding="utf-8")

    entete = "," + ",".join(str(nd.index) for nd in noeuds)
    lignes_m = [entete]
    for i, nd in enumerate(noeuds):
        lignes_m.append(str(nd.index) + "," + ",".join(f"{v:.3f}" for v in matrice[i]))
    (dossier / "matrice_geodesique.csv").write_text("\n".join(lignes_m),
                                                    encoding="utf-8")
