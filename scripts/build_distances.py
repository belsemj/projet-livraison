"""Construit ou recharge la matrice de distances. --force pour recalculer."""
import sys
from app.database import SessionLocal
from app.services import distances

forcer = "--force" in sys.argv
db = SessionLocal()
try:
    matrice, noeuds, motif = distances.obtenir_matrice(db, forcer=forcer)
finally:
    db.close()

libelle = {
    "cache": "cache valide, chargement direct",
    "absent": "cache absent, calcul complet",
    "empreinte": "coordonnees modifiees, recalcul",
    "version": "format obsolete, recalcul",
    "forcee": "recalcul force",
}[motif]

print(f"{libelle}")
print(f"matrice {matrice.shape}, {len(noeuds)} noeuds")
zeros = int(((matrice == 0).sum() - matrice.shape[0]) // 2)
print(f"paires a distance nulle : {zeros}")
