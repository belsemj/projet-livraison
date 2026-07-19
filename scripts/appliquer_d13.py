"""D13 : application des coordonnees provisoires des 4 depots.
Ecrit stations.csv, puis met a jour la base par UPDATE cible.
"""
import csv
import shutil
import sqlite3
from pathlib import Path

CSV = Path("data/stations.csv")

# id_station -> (latitude, longitude) provisoires
NOUVELLES = {
    2: (37.2633, 9.8485),    # Bizerte  - Zone d'activites economiques
    3: (35.7821, 10.6686),   # Sousse   - Z.I. Sidi Abdelhamid
    4: (34.7486, 10.7733),   # Sfax     - Z.I. Poudriere 1
    5: (33.8653, 10.0852),   # Gabes    - Sidi Boulbaba
}

# --- 1. sauvegarde puis reecriture du CSV -------------------------------
shutil.copy(CSV, CSV.with_suffix(".csv.bak"))
print(f"sauvegarde -> {CSV.with_suffix('.csv.bak')}")

with CSV.open(encoding="utf-8", newline="") as f:
    lignes = list(csv.DictReader(f))
    entetes = lignes[0].keys()

modifiees = 0
for lg in lignes:
    if lg.get("type", "").lower() == "depot" or lg.get("nom", "").startswith("Depot"):
        for id_st, (lat, lon) in NOUVELLES.items():
            if lg["nom"] == f"Depot {['','El Ghazala','Bizerte','Sousse','Sfax','Gabes'][id_st]}":
                lg["latitude"], lg["longitude"] = str(lat), str(lon)
                modifiees += 1

with CSV.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=entetes)
    w.writeheader()
    w.writerows(lignes)
print(f"CSV : {modifiees} lignes modifiees")

# --- 2. UPDATE cible en base -------------------------------------------
conn = sqlite3.connect("livraison.db")
cur = conn.cursor()
for id_st, (lat, lon) in NOUVELLES.items():
    cur.execute(
        "UPDATE station SET latitude=?, longitude=? WHERE id_station=?",
        (lat, lon, id_st),
    )
conn.commit()

for id_st in NOUVELLES:
    cur.execute("SELECT nom, latitude, longitude FROM station WHERE id_station=?", (id_st,))
    print("  ", cur.fetchone())
conn.close()
print("base mise a jour")
