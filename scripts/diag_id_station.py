"""
Diagnostic LECTURE SEULE : coherence de chauffeur.id_station apres la reorg
de flotte D33 (S5 J4).

La reorganisation D33 a reaffecte le id_station des VEHICULES aux depots
(un standard + un refrigere par depot, un securise unique au depot 1). Le
binome fixe chauffeur<->vehicule (D12) n'a pas suivi : le id_station des
CHAUFFEURS appaires est reste celui d'avant la reorg. Sans impact sur le
solveur (qui lit v.id_station), mais incoherent pour l'ecran 4, qui affiche
le depot du chauffeur.

Ce script ne fait qu'observer. Il liste chaque binome appaire, compare les
deux depots et propose la correction (chauffeur suit son vehicule, D12) sans
l'appliquer. Aucune ecriture.

Invocation (depuis la racine) :
    python -m scripts.diag_id_station
"""

from app.database import SessionLocal
from app.models.vehicule import Vehicule


def main() -> None:
    db = SessionLocal()
    try:
        # Binomes appaires uniquement : un vehicule avec un chauffeur attitre.
        vehicules = (
            db.query(Vehicule)
            .filter(Vehicule.id_chauffeur.isnot(None))
            .order_by(Vehicule.id_vehicule)
            .all()
        )

        print("=" * 70)
        print("DIAGNOSTIC id_station : chauffeur vs vehicule (lecture seule)")
        print("=" * 70)
        print(f"binomes appaires (D12) : {len(vehicules)}\n")

        entete = f"{'veh':>4}  {'chauffeur':<26}  {'dep_veh':>7}  {'dep_ch':>6}  etat"
        print(entete)
        print("-" * len(entete))

        desalignes = []
        for v in vehicules:
            ch = v.chauffeur                      # relation D12 (uselist=False)
            dep_veh = v.id_station
            dep_ch = ch.id_station if ch else None
            nom = f"{ch.nom} (#{ch.id_chauffeur})" if ch else "(sans chauffeur)"
            if ch and dep_ch != dep_veh:
                etat = f"DESALIGNE -> {dep_ch} devient {dep_veh}"
                desalignes.append((v, ch, dep_ch, dep_veh))
            else:
                etat = "ok"
            dep_ch_aff = dep_ch if dep_ch is not None else "-"
            print(f"{v.id_vehicule:>4}  {nom[:26]:<26}  {dep_veh:>7}  "
                  f"{dep_ch_aff:>6}  {etat}")

        print("\n" + "-" * len(entete))
        print(f"resume : {len(desalignes)} desaligne(s) sur {len(vehicules)} binomes")

        if desalignes:
            print("\nproposition de correction (chauffeur suit son vehicule, D12) :")
            for v, ch, dep_ch, dep_veh in desalignes:
                marque = ""
                if ch.statut != "actif":
                    marque = f"   [info] chauffeur en statut '{ch.statut}'"
                print(f"  chauffeur #{ch.id_chauffeur} ({ch.nom}) : "
                      f"depot {dep_ch} -> {dep_veh}"
                      f"   (via vehicule #{v.id_vehicule}){marque}")

        print("\nAucune ecriture effectuee.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
