import sqlite3
import glob
import os

fichiers = ["livraison.db"] + sorted(glob.glob("livraison.db.*.bak"))

print(f"{'fichier':45s} {'taille':>10s} {'lots':>6s} {'veh':>5s} {'dest':>5s} {'stat':>5s}")
print("-" * 82)

for f in fichiers:
    if not os.path.exists(f):
        continue
    taille = os.path.getsize(f)
    try:
        c = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
        def q(t): return c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{f:45s} {taille:10d} {q('lot'):6d} {q('vehicule'):5d} "
              f"{q('destination'):5d} {q('station'):5d}")
        c.close()
    except Exception as e:
        print(f"{f:45s} {taille:10d}   ERREUR: {e}")

print("\n-- temoin de correction (geocodage J3) --")
for f in fichiers:
    if not os.path.exists(f):
        continue
    try:
        c = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
        r = c.execute(
            "SELECT nom, latitude, longitude FROM destination "
            "WHERE nom LIKE '%eben%' OR nom LIKE '%erkenn%' OR nom LIKE '%Hencha%'"
        ).fetchall()
        print(f"  {f}")
        for x in r:
            print(f"      {x}")
        c.close()
    except Exception:
        pass
