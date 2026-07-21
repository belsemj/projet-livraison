import re
import shutil
import datetime
import os

SEED = os.path.join("data", "seed.sql")
HORO = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

CIBLES = [
    ("chauffeur 12 : conge -> actif",
     r"INSERT INTO chauffeur .*VALUES \(12, 'Tarek F\.', 'conge', 3\);",
     lambda s: s.replace("'conge'", "'actif'")),

    ("vehicule 12 : reserve -> actif, chauffeur NULL -> 12",
     r"INSERT INTO vehicule .*VALUES \(12, .*NULL\);",
     lambda s: s.replace("'reserve'", "'actif'").replace(", NULL);", ", 12);")),

    ("destination 71 : -> Jebeniana Est",
     r"INSERT INTO destination .*VALUES \(71, 'Jebeniana',",
     lambda s: s.replace("'Jebeniana',", "'Jebeniana Est',", 1)),

    ("destination 72 : -> Jebeniana Centre",
     r"INSERT INTO destination .*VALUES \(72, 'Jebeniana',",
     lambda s: s.replace("'Jebeniana',", "'Jebeniana Centre',", 1)),
]

lignes = open(SEED, encoding="utf-8").read().splitlines(keepends=True)
modifs = []

for libelle, motif, transf in CIBLES:
    trouve = [i for i, l in enumerate(lignes) if re.search(motif, l)]
    if len(trouve) == 0:
        print(f"  [ignore] {libelle} : motif absent (deja fait ?)")
        continue
    if len(trouve) > 1:
        raise SystemExit(f"ABANDON : {len(trouve)} lignes pour '{libelle}'")
    i = trouve[0]
    modifs.append((libelle, i + 1, lignes[i].rstrip(), transf(lignes[i]).rstrip()))
    lignes[i] = transf(lignes[i])

if not modifs:
    raise SystemExit("\nRien a modifier.")

print("\n-- modifications prevues --")
for libelle, n, avant, apres in modifs:
    print(f"\n  {libelle}  (L{n})\n    avant : {avant}\n    apres : {apres}")

if input("\nAppliquer ? (o/N) ").strip().lower() != "o":
    raise SystemExit("Annule.")

shutil.copy2(SEED, f"{SEED}.{HORO}.bak")
open(SEED, "w", encoding="utf-8").writelines(lignes)
print(f"\nApplique. Sauvegarde : {SEED}.{HORO}.bak")
