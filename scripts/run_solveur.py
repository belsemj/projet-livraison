import time

from app.database import SessionLocal
from app.services.matrice_etendue import construire_contexte, controler
from app.services.solveur import resoudre, resume

db = SessionLocal()
ctx = construire_contexte(db)

anomalies = controler(ctx)
if anomalies:
    print("ANOMALIES :")
    for a in anomalies:
        print("  !", a)
    raise SystemExit(1)

print(f"contexte : {ctx.nb_noeuds} noeuds, {ctx.nb_vehicules} vehicules")
print("resolution en cours...\n")

t0 = time.perf_counter()
res = resoudre(ctx, limite_secondes=10)
duree = time.perf_counter() - t0

print(resume(res, ctx))
print(f"\ntemps de resolution : {duree:.1f} s")
db.close()
