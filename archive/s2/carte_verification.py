"""
carte_verification.py — Semaine 2, Jour 3
Projet : application web d'affectation des tâches de livraison (MDVRP).

Génère une carte interactive (Folium / Leaflet) pour vérifier visuellement
les localités signalées par verifier_geocodage.py.

Pour chaque point douteux :
  - marqueur ROUGE  = ancienne coordonnée (approximative, S1)
  - marqueur VERT   = nouvelle coordonnée (Nominatim)
  - trait gris      = déplacement entre les deux

Sortie : data/verification_carte.html  (à ouvrir dans un navigateur)

Usage (racine du projet, venv activé) :
    python carte_verification.py
"""

import csv
from pathlib import Path

import folium

FICHIER_RAPPORT = Path("data/rapport_geocodage.csv")
FICHIER_CARTE   = Path("data/verification_carte.html")

# Seuls ces statuts sont affichés (les "OK" n'ont pas besoin de contrôle).
STATUTS_A_VERIFIER = {"ÉCART FORT", "REPLI GOUV.", "NON TROUVÉ"}


def main():
    if not FICHIER_RAPPORT.exists():
        raise SystemExit(f"Lance d'abord verifier_geocodage.py. "
                         f"Fichier manquant : {FICHIER_RAPPORT.resolve()}")

    with FICHIER_RAPPORT.open(encoding="utf-8", newline="") as f:
        lignes = [r for r in csv.DictReader(f)
                  if r["statut"] in STATUTS_A_VERIFIER]

    if not lignes:
        print("Aucune localité à vérifier : tout est OK.")
        return

    # Carte centrée sur la Tunisie
    carte = folium.Map(location=[34.0, 9.5], zoom_start=7,
                       tiles="OpenStreetMap")

    for r in lignes:
        la0, lo0 = float(r["lat_ancienne"]), float(r["lon_ancienne"])
        la1, lo1 = float(r["lat_nouvelle"]), float(r["lon_nouvelle"])
        info = (f"{r['nom']} ({r['gouvernorat']})<br>"
                f"écart = {r['ecart_km']} km<br>{r['statut']}")

        folium.Marker([la0, lo0], popup=f"ANCIEN — {info}",
                      icon=folium.Icon(color="red", icon="remove")).add_to(carte)
        folium.Marker([la1, lo1], popup=f"NOUVEAU — {info}",
                      icon=folium.Icon(color="green", icon="ok")).add_to(carte)
        folium.PolyLine([[la0, lo0], [la1, lo1]],
                        color="gray", weight=2, dash_array="5").add_to(carte)

    carte.save(str(FICHIER_CARTE))
    print(f"{len(lignes)} points à vérifier -> {FICHIER_CARTE.resolve()}")
    print("Ouvre ce fichier .html dans ton navigateur.")


if __name__ == "__main__":
    main()
