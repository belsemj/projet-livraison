"""Diagnostic du lot systematiquement abandonne sous flotte reduite."""

from app.database import SessionLocal
from app.services.matrice_etendue import ECHELLE, construire_contexte
from app.services.solveur import couvre
from scripts.calibrer import reduire_flotte

ID_CIBLE = 79

db = SessionLocal()
try:
    ctx = construire_contexte(db)
finally:
    db.close()

lot = next(l for l in ctx.lots if l.id_lot == ID_CIBLE)
print(f"lot {lot.id_lot} : {lot.volume_echelle / ECHELLE:.2f} m3, "
      f"caisson {lot.caisson_requis}, dest {lot.id_destination}, "
      f"priorite {lot.priorite}")

for n in (11, 9):
    sous = reduire_flotte(ctx, n) if n < ctx.nb_vehicules else ctx
    compat = [v for v in sous.vehicules if couvre(v.type_caisson, lot.caisson_requis)]
    print(f"\nflotte {n} : {len(sous.vehicules)} vehicules, "
          f"{len(compat)} compatibles")
    for v in compat:
        marge = v.capacite_echelle - lot.volume_echelle
        print(f"  veh {v.id_vehicule:2d}  {v.type_caisson:9s}  "
              f"capacite {v.capacite_echelle / ECHELLE:5.2f}  "
              f"{'OK' if marge >= 0 else 'TROP PETIT'}")

    besoin = sum(l.volume_echelle for l in ctx.lots
                 if l.caisson_requis == lot.caisson_requis)
    dispo = sum(v.capacite_echelle for v in compat)
    print(f"  volume '{lot.caisson_requis}' total : {besoin / ECHELLE:.2f} m3")
    print(f"  capacite compatible       : {dispo / ECHELLE:.2f} m3")
