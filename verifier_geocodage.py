"""
verifier_geocodage.py — Semaine 2, Jour 3
Projet : application web d'affectation des tâches de livraison (MDVRP).

Vérifie et corrige les coordonnées GPS approximatives de data/stations.csv
en les confrontant à Nominatim (OpenStreetMap), puis produit :
  - data/coordinates_verifiees.csv : le jeu de données corrigé
  - data/rapport_geocodage.csv     : ancien vs nouveau, écart (km) et statut

Usage (depuis la racine du projet, venv activé) :
    python verifier_geocodage.py
"""

import csv
from pathlib import Path

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.distance import geodesic

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
FICHIER_ENTREE  = Path("data/stations.csv")
FICHIER_CORRIGE = Path("data/coordinates_verifiees.csv")
FICHIER_RAPPORT = Path("data/rapport_geocodage.csv")

# Noms de colonnes du CSV d'entrée — À AJUSTER si les tiens diffèrent.
COL_NOM         = "nom"
COL_GOUVERNORAT = "gouvernorat"
COL_LAT         = "latitude"
COL_LON         = "longitude"

# Au-delà de ce seuil (km), l'écart est signalé pour vérification manuelle.
SEUIL_ALERTE_KM = 5.0

# --------------------------------------------------------------------------
# Nominatim : user_agent perso obligatoire + 1 requête/seconde maximum
# --------------------------------------------------------------------------
geolocator = Nominatim(user_agent="projet-livraison-belsem")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1,
                      max_retries=2, error_wait_seconds=5.0)


def geocoder_localite(nom, gouvernorat):
    """
    Interroge Nominatim en restreignant à la Tunisie.
    Retourne (lieu, repli) où repli=True si la localité précise est
    introuvable et qu'on est retombé sur le centroïde du gouvernorat.
    """
    lieu = geocode(f"{nom}, {gouvernorat}, Tunisie",
                   country_codes="tn", exactly_one=True)
    if lieu is not None:
        return lieu, False
    # Repli : la petite localité n'est pas dans OSM -> gouvernorat seul
    lieu = geocode(f"{gouvernorat}, Tunisie", country_codes="tn")
    return lieu, True


def main():
    if not FICHIER_ENTREE.exists():
        raise SystemExit(f"Fichier introuvable : {FICHIER_ENTREE.resolve()}")

    with FICHIER_ENTREE.open(encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))

    entetes = lignes[0].keys()
    rapport = []
    print(f"Vérification de {len(lignes)} localités "
          f"(1 requête/seconde, patiente ~{len(lignes)} s)...\n")

    for i, ligne in enumerate(lignes, start=1):
        nom  = ligne[COL_NOM].strip()
        gouv = ligne[COL_GOUVERNORAT].strip()
        lat0 = float(ligne[COL_LAT])
        lon0 = float(ligne[COL_LON])

        lieu, repli = geocoder_localite(nom, gouv)

        if lieu is None:
            statut, lat1, lon1, ecart = "NON TROUVÉ", lat0, lon0, None
        else:
            lat1 = round(lieu.latitude, 6)
            lon1 = round(lieu.longitude, 6)
            ecart = round(geodesic((lat0, lon0), (lat1, lon1)).km, 2)
            if repli:
                statut = "REPLI GOUV."
            elif ecart > SEUIL_ALERTE_KM:
                statut = "ÉCART FORT"
            else:
                statut = "OK"
            # On applique la correction (sauf NON TROUVÉ où on garde l'ancien)
            ligne[COL_LAT] = lat1
            ligne[COL_LON] = lon1

        rapport.append({
            "nom": nom, "gouvernorat": gouv,
            "lat_ancienne": lat0, "lon_ancienne": lon0,
            "lat_nouvelle": lat1, "lon_nouvelle": lon1,
            "ecart_km": ecart, "statut": statut,
        })
        print(f"[{i:3}/{len(lignes)}] {nom:<20} {statut:<12} écart={ecart}")

    # Écriture du CSV corrigé (mêmes colonnes que l'entrée)
    with FICHIER_CORRIGE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=entetes)
        w.writeheader()
        w.writerows(lignes)

    # Écriture du rapport de vérification
    with FICHIER_RAPPORT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rapport[0].keys())
        w.writeheader()
        w.writerows(rapport)

    # Synthèse console
    from collections import Counter
    compte = Counter(r["statut"] for r in rapport)
    print("\n--- Synthèse ---")
    for s, n in compte.items():
        print(f"  {s:<12} : {n}")
    print(f"\nCorrigé  -> {FICHIER_CORRIGE}")
    print(f"Rapport  -> {FICHIER_RAPPORT}")
    print("À relire à la main : les lignes ÉCART FORT et REPLI GOUV.")


if __name__ == "__main__":
    main()
