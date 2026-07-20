"""
S4 J3 - Etape 2 ter : application des corrections de coordonnees validees.

Lit data/regeocodage_controle.csv, ne retient que les lignes marquees
ACCEPTE, met a jour la table destination dans livraison.db, puis
declenche la regeneration de la matrice via obtenir_matrice().

Sauvegarde horodatee de la base avant toute ecriture.
Le fichier data/seed.sql n'est PAS modifie : le script signale en fin
d'execution les lignes a y reporter manuellement.

Usage : python scripts/appliquer_corrections_coord.py
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.database import SessionLocal  # noqa: E402
from app.models.destination import Destination  # noqa: E402
from app.models.station import Station  # noqa: E402
from app.services import distances as svc  # noqa: E402

DOSSIER_DATA = RACINE / "data"
FICHIER_RAPPORT = DOSSIER_DATA / "regeocodage_controle.csv"
FICHIER_NOEUDS = DOSSIER_DATA / "noeuds.csv"
FICHIER_BASE = RACINE / "livraison.db"


def sauvegarder_base():
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    copie = FICHIER_BASE.with_suffix(f".db.{horodatage}.bak")
    shutil.copy2(FICHIER_BASE, copie)
    print(f"Sauvegarde : {copie.name}\n")


def lire_corrections():
    """Croise le rapport d'arbitrage avec le referentiel des noeuds."""
    rapport = pd.read_csv(FICHIER_RAPPORT)
    retenues = rapport[rapport["decision"] == "ACCEPTE"].copy()

    if retenues.empty:
        sys.exit("Aucune ligne ACCEPTE dans le rapport.")

    noeuds = pd.read_csv(FICHIER_NOEUDS)
    colonne_index = "index" if "index" in noeuds.columns else noeuds.columns[0]

    fusion = retenues.merge(
        noeuds[[colonne_index, "type", "id_entite"]],
        left_on="index",
        right_on=colonne_index,
        how="left",
        suffixes=("", "_ref"),
    )

    if fusion["id_entite"].isna().any():
        sys.exit("Correspondance index -> id_entite incomplete.")

    return fusion


def appliquer(corrections):
    session = SessionLocal()
    reportables = []

    try:
        for _, ligne in corrections.iterrows():
            modele = Station if ligne["type"] == "station" else Destination
            cle = (
                modele.id_station
                if ligne["type"] == "station"
                else modele.id_destination
            )

            entite = session.query(modele).filter(cle == int(ligne["id_entite"])).first()
            if entite is None:
                print(f"  introuvable : {ligne['nom']} (id {ligne['id_entite']})")
                continue

            ancienne = (float(entite.latitude), float(entite.longitude))
            entite.latitude = round(float(ligne["lat_proposee"]), 6)
            entite.longitude = round(float(ligne["lon_proposee"]), 6)

            print(
                f"  {ligne['nom']:<22} {ancienne[0]:.6f}, {ancienne[1]:.6f}"
                f"  ->  {entite.latitude:.6f}, {entite.longitude:.6f}"
            )
            reportables.append(
                (ligne["type"], int(ligne["id_entite"]), ligne["nom"],
                 entite.latitude, entite.longitude)
            )

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return reportables


def regenerer():
    session = SessionLocal()
    try:
        matrice, noeuds, motif = svc.obtenir_matrice(session)
        print(f"\nMatrice : {matrice.shape}, motif = {motif}")
        if motif == "cache":
            print(
                "ATTENTION : le cache n'a pas ete invalide. "
                "L'empreinte n'a pas change - verifier que la mise a jour "
                "a bien ete commitee."
            )
        anomalies = svc.controler(matrice, noeuds)
        if anomalies:
            print(f"\n{len(anomalies)} anomalie(s) detectee(s) :")
            for a in anomalies[:10]:
                print(f"  {a}")
    finally:
        session.close()


def main():
    corrections = lire_corrections()
    print(f"Corrections retenues : {len(corrections)}\n")

    sauvegarder_base()
    reportables = appliquer(corrections)
    regenerer()

    print("\n" + "=" * 62)
    print("A REPORTER MANUELLEMENT DANS data/seed.sql")
    print("=" * 62)
    for type_entite, id_entite, nom, lat, lon in reportables:
        print(f"  {nom} ({type_entite} {id_entite}) : {lat:.6f}, {lon:.6f}")
    print(
        "\nSans ce report, un re-seed de la base reintroduirait "
        "les anciennes coordonnees."
    )


if __name__ == "__main__":
    main()
