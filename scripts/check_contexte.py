from app.database import SessionLocal
from app.services.matrice_etendue import construire_contexte, controler, ECHELLE

db = SessionLocal()
ctx = construire_contexte(db)

print(f"noeuds     : {ctx.nb_noeuds}  (5 stations + {len(ctx.lots)} lots + 1 arrivee)")
print(f"vehicules  : {ctx.nb_vehicules}")
print(f"matrice    : {ctx.matrice.shape}  {ctx.matrice.dtype}  statut={ctx.statut_matrice}")
print(f"charge     : {sum(ctx.demandes)/ECHELLE:.2f}  /  capacite {sum(ctx.capacites)/ECHELLE:.2f}")
print(f"starts     : {ctx.starts}")
print(f"arrivee    : index {ctx.index_arrivee}")

print("\n-- echantillon de distances (metres) --")
print(f"  station0 -> station1 : {ctx.matrice[0, 1]}")
print(f"  lot#1    -> arrivee  : {ctx.matrice[5, ctx.index_arrivee]}")
print(f"  max      : {ctx.matrice.max()}")

par_dest = {}
for l in ctx.lots:
    par_dest.setdefault(l.id_destination, []).append(l)
jum = [g for g in par_dest.values() if len(g) > 1]
print(f"\n-- jumeaux : {len(jum)} destinations a 2 lots --")
for g in jum[:3]:
    print(f"  dest {g[0].id_destination} : lots {[l.id_lot for l in g]}, "
          f"d = {ctx.matrice[g[0].index, g[1].index]} m")

print("\n-- controles --")
anomalies = controler(ctx)
if anomalies:
    for x in anomalies:
        print("  !", x)
else:
    print("  aucune anomalie")

db.close()
