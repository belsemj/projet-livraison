"""
Supprime les lots de test residuels (defaut 121-129)

Ces lots sont des doublons de saisie qui saturaient volontairement les depots
pour tester l'abandon. Une fois la fonctionnalite validee, on rend la
base de demo propre.

Deux temps (regle "audit avant write") :
    python -m scripts.supprimer_lots_test              # AUDIT seul (dry-run)
    python -m scripts.supprimer_lots_test --confirmer  # supprime

Prealable : purger les runs d'abord (python -m scripts.vider_runs). Ce script
REFUSE de supprimer un lot encore reference par une affectation ou une ligne
lot_non_servi -- sinon il corromprait un run persiste. L'audit le signale et
sort en erreur sans rien ecrire.
"""

import argparse

from app.database import SessionLocal
from app.models.lot import Lot
from app.models.affectation import Affectation
from app.models.lot_non_servi import LotNonServi

BORNE_MIN = 121
BORNE_MAX = 129


def main() -> None:
    p = argparse.ArgumentParser(description="Suppression des lots de test")
    p.add_argument("--min", type=int, default=BORNE_MIN)
    p.add_argument("--max", type=int, default=BORNE_MAX)
    p.add_argument("--confirmer", action="store_true",
                   help="execute la suppression (sinon audit seul)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        lots = (
            db.query(Lot.id_lot, Lot.id_vague, Lot.id_destination)
            .filter(Lot.id_lot >= args.min, Lot.id_lot <= args.max)
            .order_by(Lot.id_lot)
            .all()
        )
        ids = [l.id_lot for l in lots]

        print("=" * 60)
        print(f"AUDIT — lots {args.min}-{args.max} (lecture seule)")
        print("=" * 60)

        if not ids:
            print("aucun lot dans cette plage. Rien a faire.")
            return

        for l in lots:
            print(f"  lot {l.id_lot:3d}  vague={l.id_vague}  dest={l.id_destination}")
        print(f"  total : {len(ids)} lot(s)")

        nb_aff = (
            db.query(Affectation)
            .filter(Affectation.id_lot.in_(ids))
            .count()
        )
        nb_lns = (
            db.query(LotNonServi)
            .filter(LotNonServi.id_lot.in_(ids))
            .count()
        )
        print(f"  references : {nb_aff} affectation(s), "
              f"{nb_lns} ligne(s) lot_non_servi")

        if nb_aff or nb_lns:
            print("\n[REFUS] Ces lots sont encore references par des runs.")
            print("        Purge les runs d'abord :  python -m scripts.vider_runs")
            print("        (supprimer un lot d'un run persiste le corromprait.)")
            raise SystemExit(1)

        if not args.confirmer:
            print("\n[DRY-RUN] Audit seul, rien supprime.")
            print("          Relance avec --confirmer pour supprimer.")
            return

        # --- suppression, transaction unique ---------------------------------
        nb = (
            db.query(Lot)
            .filter(Lot.id_lot.in_(ids))
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"\n[OK] {nb} lot(s) supprime(s). Base de demo propre.")

    except SystemExit:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
