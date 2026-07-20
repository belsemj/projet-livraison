"""
S4 J3 - Etape 2 bis : re-geocodage controle des noeuds imprecis.

Selectionne les noeuds dont les coordonnees ont 2 decimales ou moins,
les re-interroge via Nominatim, puis arbitre chaque proposition avec
un critere objectif : le snapped_distance d'ORS (ecart au reseau routier).

Une nouvelle coordonnee n'est retenue que si :
  - elle se raccroche mieux au reseau routier que l'ancienne,
  - elle ne s'eloigne pas de plus de SEUIL_DEPLACEMENT_KM de l'ancienne
    (au-dela, le geocodeur a probablement trouve une autre localite).

AUCUNE ecriture dans noeuds.csv : le script produit un rapport a valider.

Usage : python scripts/regeocodage_controle.py
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

# --------------------------------------------------------------------------
# Parametres
# --------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DATA = RACINE / "data"

FICHIER_NOEUDS = DOSSIER_DATA / "noeuds.csv"
FICHIER_RAPPORT = DOSSIER_DATA / "regeocodage_controle.csv"

SEUIL_DECIMALES = 2          # noeuds a re-geocoder : <= 2 decimales
SEUIL_DEPLACEMENT_KM = 5.0   # au-dela, proposition jugee suspecte
GAIN_MINIMAL_M = 50          # amelioration en deca de laquelle on ne bouge pas

URL_MATRIX = "https://api.openrouteservice.org/v2/matrix/driving-car"
AGENT_NOMINATIM = "projet-livraison-s4j3"
PAUSE_NOMINATIM = 1.1        # secondes : politique d'usage de Nominatim


# --------------------------------------------------------------------------
# Selection des noeuds imprecis
# --------------------------------------------------------------------------

def compter_decimales(valeur):
    texte = str(valeur)
    return len(texte.split(".")[1]) if "." in texte else 0


def selectionner(noeuds):
    """Retient les noeuds dont la coordonnee la moins precise est <= seuil."""
    precision = noeuds.apply(
        lambda r: min(
            compter_decimales(r["latitude"]), compter_decimales(r["longitude"])
        ),
        axis=1,
    )
    return noeuds[precision <= SEUIL_DECIMALES].copy()


# --------------------------------------------------------------------------
# Re-geocodage
# --------------------------------------------------------------------------

def regeocoder(cibles):
    geocodeur = Nominatim(user_agent=AGENT_NOMINATIM, timeout=15)
    propositions = []

    for _, ligne in cibles.iterrows():
        requete = f"{ligne['nom']}, Tunisie"
        try:
            lieu = geocodeur.geocode(requete, country_codes="tn", exactly_one=True)
        except Exception as erreur:
            print(f"  {ligne['nom']:<22} erreur : {erreur}")
            lieu = None

        if lieu is None:
            propositions.append((None, None, None))
            print(f"  {ligne['nom']:<22} aucun resultat")
        else:
            deplacement = geodesic(
                (ligne["latitude"], ligne["longitude"]),
                (lieu.latitude, lieu.longitude),
            ).km
            propositions.append((lieu.latitude, lieu.longitude, deplacement))
            print(
                f"  {ligne['nom']:<22} -> {lieu.latitude:.6f}, "
                f"{lieu.longitude:.6f}  (deplacement {deplacement:.2f} km)"
            )

        time.sleep(PAUSE_NOMINATIM)

    cibles["lat_proposee"] = [p[0] for p in propositions]
    cibles["lon_proposee"] = [p[1] for p in propositions]
    cibles["deplacement_km"] = [p[2] for p in propositions]
    return cibles


# --------------------------------------------------------------------------
# Arbitrage par snapped_distance
# --------------------------------------------------------------------------

def mesurer_raccrochage(points):
    """points : liste de [longitude, latitude]. Renvoie les snapped_distance."""
    load_dotenv()
    cle = os.getenv("ORS_API_KEY")
    if not cle:
        sys.exit("ORS_API_KEY absente du fichier .env")

    reponse = requests.post(
        URL_MATRIX,
        headers={"Authorization": cle, "Content-Type": "application/json"},
        json={
            "locations": points,
            "sources": [0],
            "metrics": ["distance"],
            "units": "km",
        },
        timeout=60,
    )

    if reponse.status_code != 200:
        print("Statut HTTP :", reponse.status_code)
        print(reponse.text[:600])
        sys.exit("Requete ORS echouee.")

    return [d.get("snapped_distance") for d in reponse.json()["destinations"]]


def arbitrer(cibles):
    valides = cibles["lat_proposee"].notna()

    anciens = cibles[["longitude", "latitude"]].values.tolist()
    nouveaux = (
        cibles.loc[valides, ["lon_proposee", "lat_proposee"]].values.tolist()
    )

    ecarts = mesurer_raccrochage(anciens + nouveaux)
    cibles["snap_actuel_m"] = ecarts[: len(anciens)]

    colonne = [None] * len(cibles)
    for position, index in enumerate(cibles.index[valides]):
        colonne[cibles.index.get_loc(index)] = ecarts[len(anciens) + position]
    cibles["snap_propose_m"] = colonne

    decisions = []
    for _, ligne in cibles.iterrows():
        if pd.isna(ligne["lat_proposee"]):
            decisions.append("aucun resultat")
        elif ligne["deplacement_km"] > SEUIL_DEPLACEMENT_KM:
            decisions.append("rejet : deplacement suspect")
        elif ligne["snap_propose_m"] is None or ligne["snap_actuel_m"] is None:
            decisions.append("indetermine")
        elif ligne["snap_actuel_m"] - ligne["snap_propose_m"] < GAIN_MINIMAL_M:
            decisions.append("rejet : pas de gain")
        else:
            decisions.append("ACCEPTE")

    cibles["decision"] = decisions
    return cibles


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------

def main():
    noeuds = pd.read_csv(FICHIER_NOEUDS)
    cibles = selectionner(noeuds)
    print(f"Noeuds a re-geocoder : {len(cibles)} sur {len(noeuds)}\n")

    cibles = regeocoder(cibles)
    print("\nArbitrage par raccrochage au reseau routier...\n")
    cibles = arbitrer(cibles)

    colonnes = [
        "index", "nom", "latitude", "longitude",
        "lat_proposee", "lon_proposee", "deplacement_km",
        "snap_actuel_m", "snap_propose_m", "decision",
    ]
    rapport = cibles[[c for c in colonnes if c in cibles.columns]]
    rapport.to_csv(FICHIER_RAPPORT, index=False, encoding="utf-8")

    print(rapport.to_string(index=False))
    print("\nRepartition des decisions :")
    print(cibles["decision"].value_counts().to_string())
    print(f"\nRapport ecrit dans {FICHIER_RAPPORT.relative_to(RACINE)}")
    print("Aucune modification appliquee a noeuds.csv.")


if __name__ == "__main__":
    main()
