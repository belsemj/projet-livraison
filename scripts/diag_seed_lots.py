"""
Diagnostic LECTURE SEULE : le generateur data/seed_lots.py reproduit-il le
jeu de lots reel en base, une fois applique le facteur(division par 50) ?

On rejoue le RNG du generateur A L'IDENTIQUE (meme graine, meme sequence
sample -> [uniform, choices, random, choices] par lot) pour obtenir le volume
BRUT de chaque lot dans l'ordre d'insertion (= ordre des id_lot). On lit la
base et on compare lot par lot : champs non-volume (doivent coller a 100 %) et
volume (relation reelle base = f(brut), residu vs round(brut/50, 2)).

Aucune ecriture. sqlite3 en SELECT seul.

    python -m scripts.diag_seed_lots
    python -m scripts.diag_seed_lots autre.db      (optionnel, tests)
"""

import sqlite3
import random
import sys

DB_DEFAUT = "livraison.db"
FACTEUR_D15 = 50

PRIORITES = ["haute", "moyenne", "basse"]
PRIORITE_WEIGHTS = [0.20, 0.55, 0.25]
CAISSONS = ["standard", "refrigere", "securise"]
CAISSON_WEIGHTS = [0.80, 0.12, 0.08]


def rejouer_generateur() -> list[dict]:
    """Rejoue EXACTEMENT la sequence RNG de data/seed_lots.py."""
    random.seed(42)
    destinations = list(range(1, 101))
    extra = random.sample(destinations, 20)
    plan = destinations + extra

    genere = []
    for rang, id_dest in enumerate(plan):
        volume_brut = round(random.uniform(5, 80), 2)
        priorite = random.choices(PRIORITES, PRIORITE_WEIGHTS)[0]
        fragile = 1 if random.random() < 0.15 else 0
        caisson = random.choices(CAISSONS, CAISSON_WEIGHTS)[0]
        genere.append({
            "id_lot": rang + 1,
            "id_destination": id_dest,
            "volume_brut": volume_brut,
            "priorite": priorite,
            "fragile": fragile,
            "caisson_requis": caisson,
        })
    return genere


def lire_base(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id_lot, volume, priorite, fragile, caisson_requis, "
            "id_destination FROM lot ORDER BY id_lot"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def bloc(titre: str) -> None:
    print("\n" + "=" * 70)
    print(titre)
    print("=" * 70)


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_DEFAUT

    genere = rejouer_generateur()
    base = lire_base(db_path)

    bloc("DIAGNOSTIC seed_lots vs base (lecture seule)")
    print(f"base            : {db_path}")
    print(f"lots generes    : {len(genere)}")
    print(f"lots en base    : {len(base)}")
    if len(base) != len(genere):
        print("\n[ALERTE] nombre de lots different -- generateur non source, ou")
        print("table modifiee depuis le seed. Comparaison sur l'intersection.")

    base_par_id = {r["id_lot"]: r for r in base}

    bloc("CHAMPS NON-VOLUME (destination, priorite, fragile, caisson)")
    champs = ["id_destination", "priorite", "fragile", "caisson_requis"]
    mismatches = {c: [] for c in champs}
    apparies = 0
    for g in genere:
        b = base_par_id.get(g["id_lot"])
        if b is None:
            continue
        apparies += 1
        for c in champs:
            if b[c] != g[c]:
                mismatches[c].append((g["id_lot"], g[c], b[c]))

    total_ok = True
    for c in champs:
        nb = len(mismatches[c])
        print(f"  {c:<16} : {'OK' if nb == 0 else str(nb) + ' ecart(s)'}")
        if nb:
            total_ok = False
            for id_lot, attendu, trouve in mismatches[c][:5]:
                print(f"      lot {id_lot} : genere={attendu!r}  base={trouve!r}")
            if nb > 5:
                print(f"      ... (+{nb - 5})")
    if total_ok:
        print(f"\n  => {apparies}/{len(genere)} lots concordent sur TOUS les champs")
        print("     non-volume. Le generateur EST la source ; D15 n'a touche")
        print("     que les volumes.")

    bloc("VOLUMES : relation base <-> brut genere")
    residu_max = 0.0
    exacts_2d = 0
    hors_hypothese = []
    ratios = []
    for g in genere:
        b = base_par_id.get(g["id_lot"])
        if b is None:
            continue
        brut = g["volume_brut"]
        reel = float(b["volume"])
        candidat = round(brut / FACTEUR_D15, 2)
        residu = round(reel - candidat, 6)
        residu_max = max(residu_max, abs(residu))
        if abs(residu) < 0.005:
            exacts_2d += 1
        else:
            hors_hypothese.append((g["id_lot"], brut, candidat, reel, residu))
        if brut:
            ratios.append(reel / brut)

    total_reel = round(sum(float(b["volume"]) for b in base), 2)
    total_candidat = round(
        sum(round(g["volume_brut"] / FACTEUR_D15, 2)
            for g in genere if g["id_lot"] in base_par_id), 2)
    ratio_moyen = sum(ratios) / len(ratios) if ratios else float("nan")

    print(f"  total volumes en base            : {total_reel}")
    print(f"  total hypothese round(brut/50,2) : {total_candidat}")
    print(f"  ratio moyen base/brut            : {ratio_moyen:.6f}"
          f"   (1/50 = {1 / FACTEUR_D15:.6f})")
    print(f"  lots ou base == round(brut/50,2) : {exacts_2d}/{apparies}")
    print(f"  residu max                       : {residu_max:.4f}")

    if hors_hypothese:
        print(f"\n  {len(hors_hypothese)} lot(s) hors hypothese /50-arrondi-2d :")
        for id_lot, brut, cand, reel, res in hors_hypothese[:10]:
            print(f"    lot {id_lot:3d} : brut={brut:6.2f}  attendu={cand:.2f}  "
                  f"base={reel:.2f}  residu={res:+.2f}")
        if len(hors_hypothese) > 10:
            print(f"    ... (+{len(hors_hypothese) - 10})")
        print("\n  => l'arrondi D15 n'est pas un simple round(x/50, 2). Le detail")
        print("     ci-dessus donne la regle reelle a reproduire (ou tranche")
        print("     pour figer la base comme source).")
    else:
        print("\n  => la base est exactement round(brut/50, 2). Corriger le")
        print("     generateur revient a diviser le volume genere par 50.")

    print("\nAucune ecriture effectuee.")


if __name__ == "__main__":
    main()
