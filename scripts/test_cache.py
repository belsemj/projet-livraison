"""Test d'invalidation du cache"""
import sqlite3
from app.database import SessionLocal
from app.services import distances

DELTA = 0.01  # ~1.1 km


def build(db, libelle):
    _, noeuds, motif = distances.obtenir_matrice(db)
    print(f"  {libelle:24s} -> motif '{motif}'")
    return distances.empreinte_noeuds(noeuds)


def set_lat(valeur):
    conn = sqlite3.connect("livraison.db")
    conn.execute("UPDATE destination SET latitude=? WHERE id_destination=1", (valeur,))
    conn.commit()
    conn.close()


conn = sqlite3.connect("livraison.db")
lat0 = conn.execute(
    "SELECT latitude FROM destination WHERE id_destination=1"
).fetchone()[0]
conn.close()
print(f"latitude d'origine (destination 1) : {lat0}\n")

db = SessionLocal()
try:
    e0 = build(db, "etat initial")

    set_lat(float(lat0) + DELTA)
    print(f"\nlatitude modifiee -> {float(lat0) + DELTA}")
    e1 = build(db, "apres modification")

    set_lat(lat0)
    print(f"\nlatitude restauree -> {lat0}")
    e2 = build(db, "apres restauration")
    e3 = build(db, "appel suivant")
finally:
    db.close()

print()
print(f"empreinte modifiee differente : {e0 != e1}")
print(f"empreinte restauree identique : {e0 == e2 == e3}")
