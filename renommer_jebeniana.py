import sqlite3
import shutil
import re
import datetime
import os

HORO = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
DB = "livraison.db"
SEED = os.path.join("data", "seed.sql")

RENOMMAGES = {71: "Jebeniana Est", 72: "Jebeniana Centre"}

# ---------- 1. sauvegardes ----------
shutil.copy2(DB, f"{DB}.{HORO}.bak")
shutil.copy2(SEED, f"{SEED}.{HORO}.bak")
print(f"sauvegardes creees ({HORO})")

# ---------- 2. base ----------
c = sqlite3.connect(DB)
for idd, nouveau in RENOMMAGES.items():
    ancien = c.execute(
        "SELECT nom FROM destination WHERE id_destination = ?", (idd,)
    ).fetchone()
    if ancien is None:
        raise SystemExit(f"ABANDON : destination {idd} introuvable")
    if ancien[0] != "Jebeniana":
        raise SystemExit(f"ABANDON : destination {idd} se nomme '{ancien[0]}'")
    c.execute(
        "UPDATE destination SET nom = ? WHERE id_destination = ?", (nouveau, idd)
    )
    print(f"  db  : {idd} 'Jebeniana' -> '{nouveau}'")
c.commit()

# ---------- 3. seed.sql ----------
txt = open(SEED, encoding="utf-8").read()
for idd, nouveau in RENOMMAGES.items():
    # ancre sur l'id en debut de tuple : (71, 'Jebeniana', ...
    motif = re.compile(r"\(\s*" + str(idd) + r"\s*,\s*'Jebeniana'")
    trouves = motif.findall(txt)
    if len(trouves) != 1:
        raise SystemExit(
            f"ABANDON : {len(trouves)} occurrence(s) pour l'id {idd} dans seed.sql, "
            "1 attendue. Base modifiee, seed.sql inchange - restaurer le .bak."
        )
    txt = motif.sub(f"({idd}, '{nouveau}'", txt, count=1)
    print(f"  seed: {idd} -> '{nouveau}'")
open(SEED, "w", encoding="utf-8").write(txt)

# ---------- 4. controle ----------
print("\n-- verification --")
for r in c.execute(
    "SELECT id_destination, nom, latitude, longitude FROM destination "
    "WHERE nom LIKE 'Jebeniana%' ORDER BY id_destination"
):
    print(f"  {r}")
dbl = c.execute(
    "SELECT nom, COUNT(1) AS n FROM destination GROUP BY nom HAVING n > 1"
).fetchall()
print(f"  doublons de nom restants : {len(dbl)}")
c.close()
