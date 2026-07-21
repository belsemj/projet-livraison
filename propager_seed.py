import re
import shutil
import datetime
import sqlite3
import os

HORO = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
SEED = os.path.join("data", "seed.sql")
shutil.copy2(SEED, f"{SEED}.{HORO}.bak")
print(f"sauvegarde : {SEED}.{HORO}.bak")

txt = open(SEED, encoding="utf-8").read()

# --- Jebeniana (si non deja fait) ---
for idd, nouveau in {71: "Jebeniana Est", 72: "Jebeniana Centre"}.items():
    m = re.compile(r"\(\s*" + str(idd) + r"\s*,\s*'Jebeniana'")
    if m.search(txt):
        txt = m.sub(f"({idd}, '{nouveau}'", txt, count=1)
        print(f"  destination {idd} -> {nouveau}")
    else:
        print(f"  destination {idd} : deja renommee ou motif absent")

open(SEED, "w", encoding="utf-8").write(txt)
print("\nATTENTION : chauffeur 12 et vehicule 12 NON traites automatiquement.")
print("Lignes concernees a corriger a la main :\n")
for i, l in enumerate(open(SEED, encoding="utf-8"), 1):
    if re.search(r"\(\s*12\s*,", l) or "Tarek" in l:
        print(f"  L{i}: {l.rstrip()}")
