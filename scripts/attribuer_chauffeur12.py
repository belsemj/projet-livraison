import sqlite3
import shutil
import datetime

HORO = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
DB = "livraison.db"
shutil.copy2(DB, f"{DB}.{HORO}.bak")
print(f"sauvegarde : {DB}.{HORO}.bak")

c = sqlite3.connect(DB)

r = c.execute(
    "SELECT nom, statut, id_station FROM chauffeur WHERE id_chauffeur = 12"
).fetchone()
if r is None or r[1] != "conge":
    raise SystemExit(f"ABANDON : chauffeur 12 inattendu -> {r}")
print(f"chauffeur 12 : {r[0]}, {r[1]}, station {r[2]}")

r = c.execute(
    "SELECT id_chauffeur, id_station, type_caisson FROM vehicule WHERE id_vehicule = 12"
).fetchone()
if r is None or r[0] is not None:
    raise SystemExit(f"ABANDON : vehicule 12 deja attribue -> {r}")
print(f"vehicule 12  : station {r[1]}, {r[2]}, libre")

c.execute("UPDATE chauffeur SET statut = 'actif' WHERE id_chauffeur = 12")
c.execute("UPDATE vehicule SET id_chauffeur = 12 WHERE id_vehicule = 12")
c.commit()

print("\n-- flotte solveur (D23) --")
tot = {}
for v in c.execute(
    "SELECT v.id_vehicule, v.type_caisson, v.capacite, v.id_station "
    "FROM vehicule v JOIN chauffeur ch ON ch.id_chauffeur = v.id_chauffeur "
    "WHERE v.assurance = 1 AND ch.statut = 'actif' ORDER BY v.id_vehicule"
):
    print(f"  veh {v[0]:2d}  {v[1]:10s} cap {v[2]:3d}  station {v[3]}")
    tot[v[1]] = tot.get(v[1], 0) + v[2]
print(f"\n  {sum(1 for _ in [0])}", end="")
print(f"\r  capacites : {tot}   total {sum(tot.values())}")
c.close()
