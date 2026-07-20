"""
S4 J3 - Etape 2 : echantillon de comparaison geodesique / routier.

Tire 50 noeuds au hasard parmi les 105, interroge l'endpoint matrix
d'OpenRouteService en une seule requete (2 450 paires ordonnees),
puis compare avec la matrice geodesique du J2.

Sortie : data/echantillon_routier.csv + statistiques du ratio en console.

Usage : python scripts/echantillon_routier.py
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Parametres
# --------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DATA = RACINE / "data"

FICHIER_NOEUDS = DOSSIER_DATA / "noeuds.csv"
FICHIER_MATRICE = DOSSIER_DATA / "matrice_geodesique.npy"
FICHIER_SORTIE = DOSSIER_DATA / "echantillon_routier.csv"

TAILLE_ECHANTILLON = 50
GRAINE = 42  # fixe : l'echantillon doit etre reproductible pour le rapport

URL_MATRIX = "https://api.openrouteservice.org/v2/matrix/driving-car"
DELAI = 60  # secondes

# Seuil au-dela duquel un point est juge mal raccroche au reseau routier
SEUIL_SNAP_M = 1000

# Tranches de distance geodesique (km) pour la ventilation du ratio
TRANCHES = [(0, 50), (50, 200), (200, 10000)]


# --------------------------------------------------------------------------
# Chargement des donnees locales
# --------------------------------------------------------------------------

def charger_noeuds():
    """Lit noeuds.csv et normalise les noms de colonnes lat / lon."""
    df = pd.read_csv(FICHIER_NOEUDS)

    def trouver(*candidats):
        for c in df.columns:
            if c.strip().lower() in candidats:
                return c
        return None

    col_lat = trouver("latitude", "lat")
    col_lon = trouver("longitude", "lon", "lng")

    if col_lat is None or col_lon is None:
        print("Colonnes trouvees :", list(df.columns))
        sys.exit("Impossible d'identifier les colonnes de coordonnees.")

    df = df.rename(columns={col_lat: "latitude", col_lon: "longitude"})
    df["index_noeud"] = range(len(df))
    return df


def charger_matrice_geodesique(nb_noeuds):
    matrice = np.load(FICHIER_MATRICE)
    if matrice.shape != (nb_noeuds, nb_noeuds):
        sys.exit(
            f"Matrice {matrice.shape} incoherente avec {nb_noeuds} noeuds. "
            "Regenerer via scripts/build_distances.py."
        )
    return matrice


# --------------------------------------------------------------------------
# Appel ORS
# --------------------------------------------------------------------------

def interroger_ors(coordonnees):
    """coordonnees : liste de [longitude, latitude]. Renvoie le JSON brut."""
    load_dotenv()
    cle = os.getenv("ORS_API_KEY")
    if not cle:
        sys.exit("ORS_API_KEY absente du fichier .env")

    reponse = requests.post(
        URL_MATRIX,
        headers={"Authorization": cle, "Content-Type": "application/json"},
        json={"locations": coordonnees, "metrics": ["distance"], "units": "km"},
        timeout=DELAI,
    )

    if reponse.status_code != 200:
        print("Statut HTTP :", reponse.status_code)
        print(reponse.text[:600])
        sys.exit("Requete ORS echouee.")

    return reponse.json()


def controler_raccrochage(donnees, noeuds_ech):
    """Signale les points eloignes du reseau routier (geocodage douteux)."""
    alertes = []
    for position, source in enumerate(donnees.get("sources", [])):
        ecart = source.get("snapped_distance")
        if ecart is not None and ecart > SEUIL_SNAP_M:
            ligne = noeuds_ech.iloc[position]
            alertes.append((int(ligne["index_noeud"]), round(ecart)))
    return alertes


# --------------------------------------------------------------------------
# Comparaison
# --------------------------------------------------------------------------

def construire_comparaison(distances_ors, indices, geodesique):
    """Croise les deux matrices sur les paires i < j de l'echantillon."""
    lignes = []
    n = len(indices)

    for a in range(n):
        for b in range(a + 1, n):
            aller = distances_ors[a][b]
            retour = distances_ors[b][a]

            if aller is None or retour is None:
                continue  # paire non routable

            i, j = indices[a], indices[b]
            geo = float(geodesique[i][j])
            if geo <= 0:
                continue  # points confondus : ratio non defini

            routier = (aller + retour) / 2
            lignes.append(
                {
                    "index_i": i,
                    "index_j": j,
                    "geodesique_km": round(geo, 3),
                    "routier_km": round(routier, 3),
                    "asymetrie_km": round(abs(aller - retour), 3),
                    "ratio": round(routier / geo, 4),
                }
            )

    return pd.DataFrame(lignes)


def afficher_statistiques(df):
    print("\n" + "=" * 62)
    print(f"ECHANTILLON : {len(df)} paires exploitables")
    print("=" * 62)

    ratio = df["ratio"]
    print("\nRatio routier / geodesique - ensemble de l'echantillon")
    print(f"  moyenne      : {ratio.mean():.4f}")
    print(f"  mediane      : {ratio.median():.4f}")
    print(f"  ecart-type   : {ratio.std():.4f}")
    print(f"  minimum      : {ratio.min():.4f}")
    print(f"  maximum      : {ratio.max():.4f}")
    print(f"  coef. var.   : {ratio.std() / ratio.mean():.4%}")

    print("\nVentilation par tranche de distance geodesique")
    print(f"  {'tranche':>14} | {'n':>5} | {'moyenne':>8} | {'ecart-type':>10}")
    print("  " + "-" * 46)
    for bas, haut in TRANCHES:
        sel = df[(df["geodesique_km"] >= bas) & (df["geodesique_km"] < haut)]
        if sel.empty:
            continue
        libelle = f"{bas}-{haut} km" if haut < 10000 else f"> {bas} km"
        print(
            f"  {libelle:>14} | {len(sel):>5} | "
            f"{sel['ratio'].mean():>8.4f} | {sel['ratio'].std():>10.4f}"
        )

    asym = df["asymetrie_km"]
    print("\nAsymetrie aller / retour (km)")
    print(f"  moyenne : {asym.mean():.3f}   maximum : {asym.max():.3f}")


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------

def main():
    noeuds = charger_noeuds()
    print(f"Noeuds charges : {len(noeuds)}")

    geodesique = charger_matrice_geodesique(len(noeuds))

    generateur = np.random.default_rng(GRAINE)
    indices = sorted(
        generateur.choice(len(noeuds), size=TAILLE_ECHANTILLON, replace=False).tolist()
    )
    noeuds_ech = noeuds.iloc[indices].reset_index(drop=True)

    coordonnees = noeuds_ech[["longitude", "latitude"]].values.tolist()
    print(
        f"Echantillon : {TAILLE_ECHANTILLON} noeuds "
        f"({TAILLE_ECHANTILLON ** 2} paires demandees, graine {GRAINE})"
    )

    donnees = interroger_ors(coordonnees)

    alertes = controler_raccrochage(donnees, noeuds_ech)
    if alertes:
        print(f"\nATTENTION - {len(alertes)} point(s) eloigne(s) du reseau routier :")
        for index_noeud, ecart in alertes:
            print(f"  noeud {index_noeud} : {ecart} m")

    df = construire_comparaison(donnees["distances"], indices, geodesique)
    if df.empty:
        sys.exit("Aucune paire exploitable.")

    df.to_csv(FICHIER_SORTIE, index=False, encoding="utf-8")
    afficher_statistiques(df)
    print(f"\nDetail ecrit dans {FICHIER_SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
