"""
Remesure S5 J5 (D34) : verification du retour au depot + surcout du decoupage.

Remplace temporairement scripts/run_solveur.py pour la seance J5. Trois roles :

  1. Verifier que D34 corrige le bug : chaque vehicule utilise rentre a SON
     depot de depart (id_station_retour == id_station_depart), et aucune
     tournee ne franchit une frontiere de depot.
  2. Verifier qu'aucun arc prohibitif n'a ete emprunte (noeud virtuel jamais
     visite).
  3. Chiffrer le surcout du decoupage par source : resolution AVEC puis SANS
     la contrainte (source=False), a budget de temps egal, pour donner a
     M. Zghili un chiffre comparable au +38,1 % des caissons.

Invocation (depuis la racine) :
    python -m scripts.run_solveur_D34
"""

import time

from app.database import SessionLocal
from app.services.matrice_etendue import construire_contexte, controler
from app.services.solveur import resoudre, resume


def coherence_retours(res) -> list[str]:
    """Anomalies de retour au depot (doivent etre vides apres D34)."""
    pb = []
    for t in res.tournees:
        if not t.lots:
            continue
        if t.id_station_retour != t.id_station_depart:
            pb.append(
                f"veh {t.id_vehicule} : depart depot {t.id_station_depart} "
                f"mais retour depot {t.id_station_retour}"
            )
    return pb


def frontieres_franchies(res, ctx) -> list[str]:
    """
    Un vehicule ne doit servir que des lots de son propre depot (contrainte
    de source). On recoupe chaque lot servi avec son id_station_source.
    """
    source = {l.id_lot: l.id_station_source for l in ctx.lots}
    pb = []
    for t in res.tournees:
        for id_lot in t.lots:
            if source.get(id_lot) != t.id_station_depart:
                pb.append(
                    f"veh {t.id_vehicule} (depot {t.id_station_depart}) sert "
                    f"lot {id_lot} rattache au depot {source.get(id_lot)}"
                )
    return pb


def bloc(titre: str) -> None:
    print("\n" + "=" * 66)
    print(titre)
    print("=" * 66)


def main() -> None:
    db = SessionLocal()
    ctx = construire_contexte(db)
    db.close()

    anomalies = controler(ctx)
    infos = [a for a in anomalies if a.startswith("[info]")]
    durs = [a for a in anomalies if not a.startswith("[info]")]

    bloc("CONTROLE DU CONTEXTE")
    if durs:
        print("ANOMALIES BLOQUANTES :")
        for a in durs:
            print("  !", a)
        raise SystemExit(1)
    if infos:
        print("Informations (abandons attendus par disjonction) :")
        for a in infos:
            print("  -", a)
    else:
        print("Aucune information ni anomalie.")
    print(f"\ncontexte : {ctx.nb_noeuds} noeuds, {ctx.nb_vehicules} vehicules")

    # --- resolution AVEC contrainte de source (production) ----------------
    bloc("RESOLUTION AVEC CONTRAINTE DE SOURCE (D33 + D34)")
    t0 = time.perf_counter()
    res = resoudre(ctx, source=True)
    duree = time.perf_counter() - t0
    print(resume(res, ctx))
    print(f"\ntemps de resolution : {duree:.1f} s")

    # --- verifications D34 ------------------------------------------------
    bloc("VERIFICATIONS D34")
    pb_retour = coherence_retours(res)
    pb_front = frontieres_franchies(res, ctx)

    if not pb_retour:
        print("[OK] Chaque vehicule utilise rentre a son depot de depart.")
    else:
        print("[ECHEC] Retours incoherents :")
        for p in pb_retour:
            print("   ", p)

    if not pb_front:
        print("[OK] Aucune tournee ne franchit de frontiere de depot.")
    else:
        print("[ECHEC] Tournees inter-depots :")
        for p in pb_front:
            print("   ", p)

    # --- resolution SANS contrainte de source (comparaison) ---------------
    bloc("RESOLUTION SANS CONTRAINTE DE SOURCE (reference J3)")
    t0 = time.perf_counter()
    res_libre = resoudre(ctx, source=False)
    duree_libre = time.perf_counter() - t0
    print(resume(res_libre, ctx))
    print(f"\ntemps de resolution : {duree_libre:.1f} s")

    # --- surcout du decoupage ---------------------------------------------
    bloc("SURCOUT DU DECOUPAGE PAR SOURCE")
    d_source = res.distance_totale_m / 1000
    d_libre = res_libre.distance_totale_m / 1000
    servis_source = len(ctx.lots) - len(res.lots_non_servis)
    servis_libre = len(ctx.lots) - len(res_libre.lots_non_servis)
    print(f"  avec source : {d_source:8.1f} km, {servis_source}/{len(ctx.lots)} lots, "
          f"{res.nb_vehicules_utilises} vehicules")
    print(f"  sans source : {d_libre:8.1f} km, {servis_libre}/{len(ctx.lots)} lots, "
          f"{res_libre.nb_vehicules_utilises} vehicules")
    if d_libre > 0:
        surcout = 100 * (d_source - d_libre) / d_libre
        print(f"\n  surcout distance du decoupage : {surcout:+.1f} %")
    print("\n  Note : 'sans source' n'impose pas le retour au depot de depart")
    print("  (les deux modeles partagent le meme code ; sans source, un")
    print("  vehicule peut encore etre affecte a un lot d'un autre depot).")
    print("  Le chiffre mesure l'effet combine du rattachement, a presenter")
    print("  comme tel a M. Zghili.")


if __name__ == "__main__":
    main()
