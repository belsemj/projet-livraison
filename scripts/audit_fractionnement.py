"""

Identifie les lots "trop gros" pour le fractionnement CIBLE : ceux dont le
volume depasse la capacite du plus gros vehicule autorise de leur depot
(meme id_station_source + caisson compatible). Ce sont les SEULS lots que le
fractionnement decoupera ; tous les autres restent un noeud unique.

Pour chaque lot trop gros, calcule le decoupage retenu :
    k    = plafond(V / c_max)      # plus petit nombre de parts
    part = V / k                    # parts egales, jamais de miettes

Verifie aussi la faisabilite "tout-ou-rien" : si la capacite AUTORISEE TOTALE
du depot (somme des camions compatibles) est elle-meme < V, meme fractionne le
lot restera abandonne -- on le signale comme BLOQUE, pas comme fractionnable.

N'ecrit rien : ni base, ni fichier. Sert a mesurer la portee avant de coder.

Usage :
    python -m scripts.audit_fractionnement            # tous les lots de la base
    python -m scripts.audit_fractionnement vague_XXXX  # une vague precise
"""

import math
import sys

from app.database import get_db
from app.models.lot import Lot
from app.services.matrice_etendue import charger_flotte
from app.services.solveur import couvre


def main() -> None:
    id_vague = sys.argv[1] if len(sys.argv) > 1 else None
    db = next(get_db())

    flotte = charger_flotte(db)  # vehicules mobilisables (D23)

    q = db.query(Lot)
    if id_vague:
        q = q.filter(Lot.id_vague == id_vague)
    lots = q.order_by(Lot.id_lot).all()

    portee = f"vague {id_vague}" if id_vague else "toute la base"
    print(f"Flotte mobilisable : {len(flotte)} vehicules")
    print(f"Lots analyses      : {len(lots)} ({portee})")
    print("-" * 82)

    n_ok = n_frac = n_bloque = 0

    for lot in lots:
        vol = float(lot.volume)
        autorises = [
            v for v in flotte
            if couvre(v.type_caisson, lot.caisson_requis)
            and (lot.id_station_source is None or v.id_station == lot.id_station_source)
        ]

        # Cas 1 : aucun vehicule autorise (caisson absent au depot, ou source manquante)
        if not autorises:
            n_bloque += 1
            print(f"lot {lot.id_lot:>4} | {vol:5.1f} m3 | {lot.caisson_requis:9} | "
                  f"depot {lot.id_station_source} | BLOQUE : aucun vehicule autorise")
            continue

        c_max = max(float(v.capacite) for v in autorises)
        c_tot = sum(float(v.capacite) for v in autorises)

        # Cas 2 : tient dans un camion -> rien a faire
        if vol <= c_max:
            n_ok += 1
            continue

        # Cas 3 : trop gros -> fractionnement cible
        k = math.ceil(vol / c_max)
        part = vol / k
        faisable = vol <= c_tot  # tout-ou-rien : la somme du depot doit suffire

        if faisable:
            n_frac += 1
            etat = f"-> FRACTIONNER en {k} parts de {part:.2f} m3"
        else:
            n_bloque += 1
            etat = "-> BLOQUE : capacite totale du depot insuffisante"

        print(f"lot {lot.id_lot:>4} | {vol:5.1f} m3 | {lot.caisson_requis:9} | "
              f"depot {lot.id_station_source} | c_max={c_max:>4.0f} c_tot={c_tot:>4.0f} | {etat}")

    print("-" * 82)
    print(f"Tiennent dans un camion   : {n_ok}")
    print(f"A fractionner (cible)     : {n_frac}")
    print(f"Bloques (irrecevables)    : {n_bloque}")
    if n_frac == 0 and not id_vague:
        print("\n=> Aucun lot de base a fractionner : la brique n'ajoute aucun noeud")
        print("   pour les donnees existantes. Recalibration attendue quasi nulle.")


if __name__ == "__main__":
    main()
