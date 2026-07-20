"""
Construction, controle et mise en cache de la matrice de distances
geodesiques (BF2).

Ordre canonique des noeuds :
    index 0 .. 4    -> stations (depots), id_station croissant
    index 5 .. 104  -> destinations, id_destination croissant

Cette convention d'index est partagee avec le solveur OR-Tools (S5)
et ne doit plus etre modifiee une fois la matrice generee.

D13 : la matrice stockee reste brute (distances geodesiques exactes).
Le plancher applique aux noeuds geographiquement confondus est une regle
metier, portee par matrice_pour_solveur() et non par le stockage.

D14 : les coordonnees des 4 depots regionaux, initialement confondues avec
le chef-lieu de leur gouvernorat, ont ete re-geocodees en zone industrielle
a titre provisoire. D14 traite la cause, D13 couvrait le symptome : depuis
D14 la matrice ne contient plus de distance nulle hors diagonale, et
matrice_pour_solveur() devient un garde-fou dormant.

Cache (S4 J2) : la matrice est persistee dans data/ et accompagnee d'un
temoin d'integrite (matrice_meta.json). obtenir_matrice() recharge le cache
s'il est valide et le reconstruit sinon.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from geopy.distance import geodesic

from app.models.station import Station
from app.models.destination import Destination

NB_STATIONS = 5
DOSSIER_DONNEES = Path("data")

# Version du format de cache. A incrementer si la structure des fichiers
# persistes change : force le recalcul chez tous les utilisateurs.
VERSION_FORMAT = 1

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

    Depuis D14 aucune paire n'est plus concernee ; la fonction est conservee
    comme garde-fou si une future destination venait a coincider avec un depot.

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


# ---------------------------------------------------------------------------
# Couche de persistance et de cache (S4 J2)
# ---------------------------------------------------------------------------

def empreinte_noeuds(noeuds: list[Noeud]) -> str:
    """
    Empreinte SHA-256 de l'ensemble ordonne des noeuds.

    Porte sur (index, type, id, latitude, longitude) : toute correction de
    coordonnees, tout ajout ou retrait de noeud change l'empreinte et invalide
    le cache. La creation d'un lot ne change rien : un lot n'est pas un noeud.
    """
    h = hashlib.sha256()
    for nd in noeuds:
        h.update(f"{nd.index}|{nd.type}|{nd.id_entite}|"
                 f"{nd.latitude:.6f}|{nd.longitude:.6f}\n".encode("utf-8"))
    return h.hexdigest()


def ecrire_metadonnees(noeuds: list[Noeud], dossier: Path = DOSSIER_DONNEES) -> None:
    """Ecrit data/matrice_meta.json (temoin d'integrite du cache)."""
    dossier.mkdir(exist_ok=True)
    meta = {
        "version_format": VERSION_FORMAT,
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nb_noeuds": len(noeuds),
        "nb_stations": NB_STATIONS,
        "type_distance": "geodesique_km",
        "empreinte": empreinte_noeuds(noeuds),
    }
    (dossier / "matrice_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def lire_metadonnees(dossier: Path = DOSSIER_DONNEES) -> dict | None:
    """Renvoie le contenu de matrice_meta.json, ou None s'il est absent/illisible."""
    chemin = dossier / "matrice_meta.json"
    if not chemin.exists():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def obtenir_matrice(db, dossier: Path = DOSSIER_DONNEES,
                    forcer: bool = False) -> tuple[np.ndarray, list[Noeud], str]:
    """
    Renvoie (matrice, noeuds, motif).

    Charge le cache s'il est valide, le reconstruit sinon. Le motif indique
    ce qui s'est passe : 'cache', 'absent', 'empreinte', 'version' ou 'forcee'.
    """
    noeuds = charger_noeuds(db)
    chemin_npy = dossier / "matrice_geodesique.npy"

    motif = None
    if forcer:
        motif = "forcee"
    elif not chemin_npy.exists():
        motif = "absent"
    else:
        meta = lire_metadonnees(dossier)
        if meta is None:
            motif = "absent"
        elif meta.get("version_format") != VERSION_FORMAT:
            motif = "version"
        elif meta.get("empreinte") != empreinte_noeuds(noeuds):
            motif = "empreinte"

    if motif is None:
        return np.load(chemin_npy), noeuds, "cache"

    matrice = construire_matrice(noeuds)
    anomalies = controler(matrice, noeuds)
    for a in anomalies:
        print(f"  [ANOMALIE] {a}")
    sauvegarder(matrice, noeuds, dossier)
    ecrire_metadonnees(noeuds, dossier)
    return matrice, noeuds, motif

# ---------------------------------------------------------------------------
# Matrice routiere (S4 J3) - lecture seule
# ---------------------------------------------------------------------------
#
# Contrairement a la matrice geodesique, la matrice routiere ne peut pas etre
# reconstruite a la demande : elle exige la cle OpenRouteService et 4 requetes
# reseau. Le service se contente donc de la lire et de signaler son etat ;
# la regeneration reste du ressort de scripts/build_distances.py.
#
# D16 : la matrice routiere est asymetrique. L'ordre (i, j) est significatif,
# controler() ne lui est donc pas applicable.


FICHIER_ROUTIER = "matrice_routiere.npy"
META_ROUTIER = "matrice_routiere_meta.json"


def lire_metadonnees_routieres(dossier: Path = DOSSIER_DONNEES) -> dict | None:
    chemin = dossier / META_ROUTIER
    if not chemin.exists():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def controler_routier(matrice: np.ndarray, noeuds: list[Noeud]) -> list[str]:
    """
    Controles applicables a une matrice asymetrique : dimension, diagonale
    nulle, absence de zero hors diagonale. La symetrie n'est PAS verifiee.
    """
    anomalies: list[str] = []
    n = len(noeuds)
    if matrice.shape != (n, n):
        anomalies.append(f"dimension {matrice.shape}, attendue ({n}, {n})")
        return anomalies
    if not np.allclose(np.diag(matrice), 0):
        anomalies.append("diagonale non nulle")
    hors_diag = ~np.eye(n, dtype=bool)
    for i, j in np.argwhere((matrice == 0) & hors_diag):
        anomalies.append(
            f"distance routiere nulle de {noeuds[i].nom} (index {i}) vers "
            f"{noeuds[j].nom} (index {j})"
        )
    return anomalies


def obtenir_matrice_routiere(db, dossier: Path = DOSSIER_DONNEES
                             ) -> tuple[np.ndarray, list[Noeud], str]:
    """
    Renvoie (matrice, noeuds, statut).

    statut : 'valide'   -> fichier present, empreinte conforme
             'perimee'  -> fichier present mais noeuds modifies depuis la
                           generation : la matrice est servie telle quelle,
                           l'appelant doit alerter.

    Leve FileNotFoundError si la matrice ou son temoin sont absents : il faut
    alors relancer scripts/build_distances.py.
    """
    noeuds = charger_noeuds(db)
    chemin = dossier / FICHIER_ROUTIER

    if not chemin.exists():
        raise FileNotFoundError(
            f"{chemin} absente : relancer scripts/build_distances.py"
        )
    meta = lire_metadonnees_routieres(dossier)
    if meta is None:
        raise FileNotFoundError(
            f"{dossier / META_ROUTIER} absent ou illisible : "
            "matrice routiere non certifiable"
        )

    matrice = np.load(chemin)
    statut = "valide" if meta.get("empreinte") == empreinte_noeuds(noeuds) else "perimee"
    return matrice, noeuds, statut
