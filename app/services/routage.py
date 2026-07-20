"""
Matrice de distances routieres (OpenRouteService).

Pendant routier de app/services/distances.py. Meme ordre canonique des
noeuds, meme mecanisme d'empreinte SHA-256, meme politique de cache.

Differences avec la matrice geodesique :
  - la matrice n'est PAS symetrique (sens uniques, echangeurs) ;
  - certaines paires peuvent etre non routables (renvoyees a None par ORS) ;
  - la generation depend d'un service externe et d'un quota.

D17 (en attente) : Kerkennah est une ile desservie par ferry. ORS modelise
la traversee comme un troncon routier ordinaire et renvoie une distance
plausible, ce qui masque la duree reelle, les horaires et la capacite du
bac. Les noeuds insulaires sont donc marques ici mais AUCUNE regle n'est
appliquee tant que la decision n'est pas prise.
"""

import json
import os
import time
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv

from app.services.distances import (
    DOSSIER_DONNEES,
    charger_noeuds,
    empreinte_noeuds,
)

URL_MATRIX = "https://api.openrouteservice.org/v2/matrix/driving-car"

# 3 500 paires maximum par requete : 33 sources x 105 destinations = 3 465
TAILLE_BLOC = 33
PAUSE_ENTRE_BLOCS = 2.0  # secondes (limite de 40 requetes/minute)
DELAI = 120

FICHIER_NPY = "matrice_routiere.npy"
FICHIER_CSV = "matrice_routiere.csv"
FICHIER_META = "matrice_routiere_meta.json"

# Noeuds non accessibles par la route seule - voir D17
NOMS_INSULAIRES = {"Kerkennah"}


class ErreurRoutage(RuntimeError):
    """Echec de generation de la matrice routiere."""


# --------------------------------------------------------------------------
# Appel du service
# --------------------------------------------------------------------------

def _cle_api() -> str:
    load_dotenv()
    cle = os.getenv("ORS_API_KEY")
    if not cle:
        raise ErreurRoutage("ORS_API_KEY absente du fichier .env")
    return cle


def _interroger_bloc(cle, points, indices_sources):
    reponse = requests.post(
        URL_MATRIX,
        headers={"Authorization": cle, "Content-Type": "application/json"},
        json={
            "locations": points,
            "sources": indices_sources,
            "destinations": list(range(len(points))),
            "metrics": ["distance"],
            "units": "km",
        },
        timeout=DELAI,
    )

    if reponse.status_code != 200:
        raise ErreurRoutage(
            f"ORS a renvoye {reponse.status_code} : {reponse.text[:300]}"
        )

    return reponse.json()["distances"]


def construire_matrice(noeuds, journal=print) -> tuple[np.ndarray, list]:
    """
    Interroge ORS par blocs de sources et assemble la matrice complete.

    Renvoie (matrice, paires_non_routables). Les paires non routables
    portent np.nan : le choix de leur traitement appartient a l'appelant,
    pas a cette couche.
    """
    cle = _cle_api()
    points = [[float(nd.longitude), float(nd.latitude)] for nd in noeuds]
    n = len(points)

    matrice = np.full((n, n), np.nan, dtype=float)
    non_routables = []

    blocs = [list(range(d, min(d + TAILLE_BLOC, n))) for d in range(0, n, TAILLE_BLOC)]
    journal(f"Generation routiere : {n} noeuds, {len(blocs)} requete(s)")

    for numero, sources in enumerate(blocs, start=1):
        journal(
            f"  bloc {numero}/{len(blocs)} : sources {sources[0]}-{sources[-1]} "
            f"({len(sources) * n} paires)"
        )
        lignes = _interroger_bloc(cle, points, sources)

        for position, index_source in enumerate(sources):
            for index_dest, valeur in enumerate(lignes[position]):
                if valeur is None:
                    non_routables.append((index_source, index_dest))
                else:
                    matrice[index_source][index_dest] = float(valeur)

        if numero < len(blocs):
            time.sleep(PAUSE_ENTRE_BLOCS)

    np.fill_diagonal(matrice, 0.0)
    return matrice, non_routables


# --------------------------------------------------------------------------
# Controles
# --------------------------------------------------------------------------

def controler(matrice, noeuds, matrice_geodesique=None) -> list[str]:
    """Anomalies structurelles. Ne leve pas : renvoie des messages."""
    anomalies = []
    n = len(noeuds)

    manquantes = int(np.isnan(matrice).sum())
    if manquantes:
        anomalies.append(f"{manquantes} distance(s) non calculee(s)")

    for i in range(n):
        for j in range(n):
            if i != j and matrice[i][j] == 0:
                anomalies.append(
                    f"distance routiere nulle entre {noeuds[i].nom} et {noeuds[j].nom}"
                )

    if matrice_geodesique is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(matrice_geodesique > 0, matrice / matrice_geodesique, np.nan)
        suspects = np.argwhere(ratio > 4)
        for i, j in suspects[:10]:
            anomalies.append(
                f"ratio {ratio[i][j]:.1f} entre {noeuds[i].nom} et {noeuds[j].nom} "
                "- detour anormal ou coordonnee douteuse"
            )

    for index, nd in enumerate(noeuds):
        if nd.nom in NOMS_INSULAIRES:
            anomalies.append(
                f"{nd.nom} (index {index}) : noeud insulaire, traversee comptee "
                "comme route ordinaire - voir D17"
            )

    return anomalies


# --------------------------------------------------------------------------
# Persistance
# --------------------------------------------------------------------------

def sauvegarder(matrice, noeuds, dossier: Path = DOSSIER_DONNEES) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    np.save(dossier / FICHIER_NPY, matrice)

    lignes = ["," + ",".join(str(nd.index) for nd in noeuds)]
    for i, nd in enumerate(noeuds):
        valeurs = ["" if np.isnan(v) else f"{v:.3f}" for v in matrice[i]]
        lignes.append(f"{nd.index}," + ",".join(valeurs))
    (dossier / FICHIER_CSV).write_text("\n".join(lignes), encoding="utf-8")


def ecrire_metadonnees(noeuds, non_routables, dossier: Path = DOSSIER_DONNEES) -> None:
    contenu = {
        "type": "routier",
        "source": "openrouteservice / driving-car",
        "nb_noeuds": len(noeuds),
        "empreinte": empreinte_noeuds(noeuds),
        "symetrique": False,
        "paires_non_routables": [list(p) for p in non_routables],
    }
    (dossier / FICHIER_META).write_text(
        json.dumps(contenu, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def lire_metadonnees(dossier: Path = DOSSIER_DONNEES) -> dict | None:
    chemin = dossier / FICHIER_META
    if not chemin.exists():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------
# Point d'entree
# --------------------------------------------------------------------------

def obtenir_matrice(db, dossier: Path = DOSSIER_DONNEES, forcer: bool = False,
                    journal=print):
    """
    Renvoie (matrice, noeuds, motif).

    motif vaut 'cache', 'absente', 'empreinte' ou 'forcee'. Toute
    regeneration consomme du quota ORS : elle n'a lieu que si les noeuds
    ont change ou si forcer=True.
    """
    noeuds = charger_noeuds(db)
    chemin_npy = dossier / FICHIER_NPY
    meta = lire_metadonnees(dossier)

    if forcer:
        motif = "forcee"
    elif not chemin_npy.exists() or meta is None:
        motif = "absente"
    elif meta.get("empreinte") != empreinte_noeuds(noeuds):
        motif = "empreinte"
    else:
        return np.load(chemin_npy), noeuds, "cache"

    journal(f"Regeneration de la matrice routiere (motif : {motif})")
    matrice, non_routables = construire_matrice(noeuds, journal=journal)

    if non_routables:
        journal(f"  {len(non_routables)} paire(s) non routable(s)")

    sauvegarder(matrice, noeuds, dossier)
    ecrire_metadonnees(noeuds, non_routables, dossier)
    return matrice, noeuds, motif
