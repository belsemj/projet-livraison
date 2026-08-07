"""
application des arbitrages du superviseur.

Kerkennah (ile desservie par ferry) est remplacee par Jebeniana,
      localite continentale du gouvernorat de Sfax. Le jeu de donnees
      etant un jeu de test (Q1), le remplacement preserve les
      100 destinations sans introduire de contrainte maritime.

El Hencha est repositionnee sur les coordonnees validees.

Les coordonnees de Jebeniana sont obtenues par geocodage puis
controlees par le snapped_distance d'ORS avant ecriture.

Usage : python scripts/appliquer_arbitrages_d17.py
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from geopy.geocoders import Nominatim

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.database import SessionLocal  # noqa: E402
from app.models.destination import Destination  # noqa: E402
from app.services import distances as svc_geo  # noqa: E402
from app.services import routage as svc_route  # noqa: E402

FICHIER_BASE = RACINE / "livraison.db"
URL_MATRIX = "https://api.openrouteservice.org/v2/matrix/driving-car"

# Arbitrages
ID_KERKENNAH = 71
NOUVEAU_NOM = "Jebeniana"
ID_EL_HENCHA = 73
EL_HENCHA_COORD = (35.122888, 10.741542)

SEUIL_SNAP_M = 500


def sauvegarder_base():
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    copie = FICHIER_BASE.with_suffix(f".db.{horodatage}.bak")
    shutil.copy2(FICHIER_BASE, copie)
    print(f"Sauvegarde : {copie.name}\n")


def geocoder_jebeniana():
    geocodeur = Nominatim(user_agent="projet-livraison-s4j3", timeout=15)
    lieu = geocodeur.geocode(f"{NOUVEAU_NOM}, Sfax, Tunisie", country_codes="tn")
    if lieu is None:
        sys.exit(f"Geocodage de {NOUVEAU_NOM} sans resultat.")
    print(f"{NOUVEAU_NOM} : {lieu.latitude:.6f}, {lieu.longitude:.6f}")
    return round(lieu.latitude, 6), round(lieu.longitude, 6)


def controler_raccrochage(coordonnees):
    """Verifie que les nouveaux points sont proches du reseau routier."""
    load_dotenv()
    cle = os.getenv("ORS_API_KEY")
    if not cle:
        sys.exit("ORS_API_KEY absente du fichier .env")

    points = [[lon, lat] for lat, lon in coordonnees]
    reponse = requests.post(
        URL_MATRIX,
        headers={"Authorization": cle, "Content-Type": "application/json"},
        json={"locations": points, "sources": [0], "metrics": ["distance"]},
        timeout=60,
    )
    if reponse.status_code != 200:
        sys.exit(f"ORS {reponse.status_code} : {reponse.text[:300]}")

    return [d.get("snapped_distance") for d in reponse.json()["destinations"]]


def appliquer(coord_jebeniana):
    session = SessionLocal()
    try:
        kerkennah = session.get(Destination, ID_KERKENNAH)
        el_hencha = session.get(Destination, ID_EL_HENCHA)

        if kerkennah is None or el_hencha is None:
            sys.exit("Destination introuvable - verifier les identifiants.")

        print(f"\n  {kerkennah.nom} -> {NOUVEAU_NOM} (D17)")
        kerkennah.nom = NOUVEAU_NOM
        kerkennah.latitude, kerkennah.longitude = coord_jebeniana

        print(
            f"  {el_hencha.nom} : {el_hencha.latitude}, {el_hencha.longitude}"
            f"  ->  {EL_HENCHA_COORD[0]}, {EL_HENCHA_COORD[1]} (Q-a)"
        )
        el_hencha.latitude, el_hencha.longitude = EL_HENCHA_COORD

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def regenerer():
    session = SessionLocal()
    try:
        print("\nMatrice geodesique...")
        mat_geo, noeuds, motif = svc_geo.obtenir_matrice(session)
        print(f"  {mat_geo.shape}, motif = {motif}")

        anomalies = svc_geo.controler(mat_geo, noeuds)
        if anomalies:
            print(f"  {len(anomalies)} anomalie(s) :")
            for a in anomalies[:5]:
                print(f"    {a}")

        print("\nMatrice routiere...")
        mat_route, noeuds, motif = svc_route.obtenir_matrice(session)
        print(f"  {mat_route.shape}, motif = {motif}")

        signalements = svc_route.controler(mat_route, noeuds, mat_geo)
        if signalements:
            print(f"  {len(signalements)} signalement(s) :")
            for s in signalements[:5]:
                print(f"    {s}")
        else:
            print("  aucun signalement")

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(mat_geo > 0, mat_route / mat_geo, np.nan)
        valeurs = ratio[np.isfinite(ratio)]
        print("\nRatio routier / geodesique")
        print(f"  moyenne : {valeurs.mean():.4f}   ecart-type : {valeurs.std():.4f}")
        print(f"  min / max : {valeurs.min():.4f} / {valeurs.max():.4f}")
    finally:
        session.close()


def main():
    coord = geocoder_jebeniana()

    ecarts = controler_raccrochage([coord, EL_HENCHA_COORD])
    print(f"\nRaccrochage au reseau routier :")
    print(f"  {NOUVEAU_NOM}  : {ecarts[0]:.1f} m")
    print(f"  El Hencha   : {ecarts[1]:.1f} m")

    if any(e is not None and e > SEUIL_SNAP_M for e in ecarts):
        sys.exit(
            f"\nUn point depasse {SEUIL_SNAP_M} m du reseau routier. "
            "Aucune modification appliquee."
        )

    sauvegarder_base()
    appliquer(coord)
    regenerer()

    print("\n" + "=" * 62)
    print("A REPORTER DANS data/seed.sql")
    print("=" * 62)
    print(
        f"  destination {ID_KERKENNAH} : nom 'Kerkennah' -> '{NOUVEAU_NOM}', "
        f"coordonnees {coord[0]}, {coord[1]}"
    )
    print(
        f"  destination {ID_EL_HENCHA} : coordonnees "
        f"{EL_HENCHA_COORD[0]}, {EL_HENCHA_COORD[1]}"
    )


if __name__ == "__main__":
    main()
