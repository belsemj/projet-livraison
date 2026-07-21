"""
Harnais de calibration du solveur MDVRP -- S5 J3.

Trois campagnes, une seule lecture de la base :
    temps       : balayage de la limite de temps
    strategies  : matrice FirstSolutionStrategy x metaheuristique
    penalite    : declenchement de l'abandon a flotte reduite

Chaque campagne ecrit un CSV horodate dans resultats/. Les mesures du
rapport doivent etre tracables : le solveur n'est pas deterministe a
budget de temps fixe, un CSV regenere ne redonnera pas les memes chiffres.

Usage (depuis la racine du projet) :
    python -m scripts.calibrer temps
    python -m scripts.calibrer strategies --limite 60
    python -m scripts.calibrer penalite --limite 60
"""

import argparse
import csv
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal
from app.services.matrice_etendue import (
    ContexteSolveur,
    construire_contexte,
    controler,
)
from app.services.solveur import CAISSONS_COUVERTS, resoudre

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "resultats"

COLONNES = [
    "campagne", "horodatage", "limite_s", "penalite", "caissons",
    "premiere_solution", "metaheuristique", "nb_vehicules", "statut",
    "distance_km", "vehicules_utilises", "lots_servis", "lots_non_servis",
    "ids_non_servis", "duree_s",
]


# ---------------------------------------------------------------------------
# Flotte reduite
# ---------------------------------------------------------------------------

def reduire_flotte(ctx: ContexteSolveur, n: int,
                   couvrir_caissons: bool = True) -> ContexteSolveur:
    """
    Derive un contexte a n vehicules.

    Les rangs OR-Tools doivent rester contigus a partir de 0 : on ne
    filtre pas, on renumerote. starts, ends et capacites sont indexes par
    rang, ils sont reconstruits en consequence.

    couvrir_caissons=True garantit au moins un vehicule de chaque type
    present dans la flotte d'origine. Sans cela, la disparition du dernier
    refrigere fait lever _restreindre_par_caisson() avant toute resolution
    -- on mesurerait une infaisabilite structurelle, pas une penalite.
    """
    if n > ctx.nb_vehicules:
        raise ValueError(f"{n} > flotte disponible ({ctx.nb_vehicules})")

    retenus = []
    if couvrir_caissons:
        vus: set[str] = set()
        for v in ctx.vehicules:
            if v.type_caisson not in vus:
                retenus.append(v)
                vus.add(v.type_caisson)
        if len(retenus) > n:
            raise ValueError(
                f"n={n} insuffisant : {len(retenus)} types de caisson a couvrir"
            )
    for v in ctx.vehicules:
        if len(retenus) >= n:
            break
        if v not in retenus:
            retenus.append(v)

    retenus.sort(key=lambda v: v.id_vehicule)
    vehicules = [replace(v, rang=i) for i, v in enumerate(retenus)]

    return replace(
        ctx,
        vehicules=vehicules,
        capacites=[v.capacite_echelle for v in vehicules],
        starts=[v.index_depart for v in vehicules],
        ends=[ctx.index_arrivee] * len(vehicules),
    )


# ---------------------------------------------------------------------------
# Mesure elementaire
# ---------------------------------------------------------------------------

def mesurer(ctx: ContexteSolveur, campagne: str, **kw) -> dict:
    t0 = time.perf_counter()
    res = resoudre(ctx, **kw)
    duree = time.perf_counter() - t0

    ligne = {
        "campagne": campagne,
        "horodatage": datetime.now().isoformat(timespec="seconds"),
        "limite_s": kw.get("limite_secondes", ""),
        "penalite": kw.get("penalite", ""),
        "caissons": kw.get("caissons", True),
        "premiere_solution": kw.get("premiere_solution", ""),
        "metaheuristique": kw.get("metaheuristique", ""),
        "nb_vehicules": ctx.nb_vehicules,
        "statut": res.statut,
        "distance_km": round(res.distance_totale_m / 1000, 1),
        "vehicules_utilises": res.nb_vehicules_utilises,
        "lots_servis": len(ctx.lots) - len(res.lots_non_servis),
        "lots_non_servis": len(res.lots_non_servis),
        "ids_non_servis": " ".join(str(i) for i in res.lots_non_servis),
        "duree_s": round(duree, 1),
    }
    print(
        f"  {campagne:10s} {ligne['distance_km']:8.1f} km  "
        f"{ligne['vehicules_utilises']:2d} veh  "
        f"{ligne['lots_servis']:3d}/{len(ctx.lots)} lots  "
        f"{ligne['duree_s']:6.1f} s"
    )
    return ligne


def ecrire(campagne: str, lignes: list[dict]) -> Path:
    SORTIE.mkdir(exist_ok=True)
    chemin = SORTIE / f"calibration_{campagne}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with chemin.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        w.writeheader()
        w.writerows(lignes)
    return chemin


# ---------------------------------------------------------------------------
# Campagnes
# ---------------------------------------------------------------------------

LIMITES = [10, 30, 60, 120, 300]

PREMIERES = ["PATH_CHEAPEST_ARC", "SAVINGS", "PARALLEL_CHEAPEST_INSERTION",
             "CHRISTOFIDES"]
METAS = ["GUIDED_LOCAL_SEARCH", "TABU_SEARCH", "SIMULATED_ANNEALING"]


def campagne_temps(ctx) -> list[dict]:
    lignes = []
    for caissons in (False, True):
        for limite in LIMITES:
            print(f"[temps] caissons={caissons} limite={limite}s")
            lignes.append(mesurer(ctx, "temps", limite_secondes=limite,
                                  caissons=caissons))
    return lignes


def campagne_strategies(ctx, limite: int) -> list[dict]:
    lignes = []
    for prem in PREMIERES:
        for meta in METAS:
            print(f"[strategies] {prem} + {meta}")
            lignes.append(mesurer(ctx, "strategies", limite_secondes=limite,
                                  caissons=True, premiere_solution=prem,
                                  metaheuristique=meta))
    return lignes


def campagne_penalite(ctx, limite: int) -> list[dict]:
    """
    Deux questions distinctes.

    Declenchement : a flotte reduite, la capacite devient insuffisante et
    l'abandon doit apparaitre. Sans caissons, pour n'isoler qu'un seul
    mecanisme -- une flotte reduite retire aussi des caissons specialises,
    et l'on ne saurait plus attribuer un abandon a la capacite ou a la
    compatibilite.

    Dissuasion : a flotte complete, une penalite abaissee doit finir par
    rendre l'abandon rentable. Si 5 000 000 m ne produit aucun abandon la
    ou 50 000 m en produit, la valeur de production est confirmee comme
    dissuasive plutot que simplement jamais sollicitee.
    """
    lignes = []

    for n in (8, 6, 4, 3):
        print(f"[penalite] flotte reduite a {n} vehicules")
        reduit = reduire_flotte(ctx, n)
        lignes.append(mesurer(reduit, "penalite", limite_secondes=limite,
                              caissons=False))

    for pen in (5_000_000, 500_000, 50_000, 5_000):
        print(f"[penalite] flotte complete, penalite={pen} m")
        lignes.append(mesurer(ctx, "penalite", limite_secondes=limite,
                              penalite=pen, caissons=False))

    return lignes


# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Calibration du solveur MDVRP")
    p.add_argument("campagne", choices=["temps", "strategies", "penalite"])
    p.add_argument("--limite", type=int, default=60,
                   help="limite de temps des campagnes strategies/penalite")
    args = p.parse_args()

    db = SessionLocal()
    try:
        ctx = construire_contexte(db)
    finally:
        db.close()

    anomalies = controler(ctx)
    if anomalies:
        print("ANOMALIES :")
        for a in anomalies:
            print("  !", a)
        raise SystemExit(1)

    types = sorted({v.type_caisson for v in ctx.vehicules})
    print(f"contexte : {ctx.nb_noeuds} noeuds, {len(ctx.lots)} lots, "
          f"{ctx.nb_vehicules} vehicules ({', '.join(types)})\n")

    if args.campagne == "temps":
        lignes = campagne_temps(ctx)
    elif args.campagne == "strategies":
        lignes = campagne_strategies(ctx, args.limite)
    else:
        lignes = campagne_penalite(ctx, args.limite)

    chemin = ecrire(args.campagne, lignes)
    print(f"\n{len(lignes)} mesures -> {chemin.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
