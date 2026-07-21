import sqlite3

c = sqlite3.connect("livraison.db")
c.row_factory = sqlite3.Row

n = c.execute("SELECT COUNT(*) AS n FROM lot").fetchone()["n"]
print("nombre de lots :", n)

print("\n-- couverture des destinations --")
r = c.execute(
    "SELECT COUNT(DISTINCT id_destination) AS d FROM lot"
).fetchone()
print(f"  {r['d']} destinations distinctes portent au moins un lot")
print("  destinations avec plusieurs lots :")
for r in c.execute(
    "SELECT id_destination, COUNT(*) AS nb FROM lot "
    "GROUP BY id_destination HAVING nb > 1 ORDER BY nb DESC LIMIT 5"
):
    print(f"    dest {r['id_destination']} : {r['nb']} lots")

print("\n-- repartition par caisson_requis --")
for r in c.execute(
    "SELECT caisson_requis AS k, COUNT(*) AS nb, SUM(volume) AS vol "
    "FROM lot GROUP BY caisson_requis"
):
    print(f"  {str(r['k']):12s} : {r['nb']:3d} lots, volume {r['vol']}")

print("\n-- priorite / fragile --")
for r in c.execute("SELECT priorite, COUNT(*) AS nb FROM lot GROUP BY priorite"):
    print(f"  priorite {r['priorite']} : {r['nb']} lots")
for r in c.execute("SELECT fragile, COUNT(*) AS nb FROM lot GROUP BY fragile"):
    print(f"  fragile {r['fragile']} : {r['nb']} lots")

print("\n-- volumes --")
r = c.execute(
    "SELECT MIN(volume) AS mn, MAX(volume) AS mx, "
    "AVG(volume) AS moy, SUM(volume) AS tot FROM lot"
).fetchone()
print(f"  min {r['mn']}  max {r['mx']}  moyenne {r['moy']:.1f}  TOTAL {r['tot']}")

print("\n-- flotte --")
for r in c.execute(
    "SELECT statut, type_caisson, COUNT(*) AS nb, SUM(capacite) AS cap "
    "FROM vehicule GROUP BY statut, type_caisson"
):
    print(f"  {r['statut']:10s} / {str(r['type_caisson']):10s} : "
          f"{r['nb']} vehicules, capacite {r['cap']}")

cap_active = c.execute(
    "SELECT SUM(capacite) AS c FROM vehicule WHERE statut = 'actif'"
).fetchone()["c"]
vol_total = c.execute("SELECT SUM(volume) AS v FROM lot").fetchone()["v"]
print(f"\n  capacite flotte active : {cap_active}")
print(f"  volume total des lots  : {vol_total}")
if cap_active:
    print(f"  RATIO charge/capacite  : {vol_total / cap_active:.2f}")

print("\n-- repartition des vehicules par station --")
for r in c.execute(
    "SELECT id_station, COUNT(*) AS nb FROM vehicule "
    "WHERE statut = 'actif' GROUP BY id_station ORDER BY id_station"
):
    print(f"  station {r['id_station']} : {r['nb']} vehicules actifs")
