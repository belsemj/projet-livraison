"""
Harnais de calibration du solveur MDVRP -- S5 J3.

Cinq campagnes, une seule lecture de la base :
    temps       : balayage de la limite de temps
    strategies  : matrice FirstSolutionStrategy x metaheuristique
    penalite    : declenchement de l'abandon a flotte reduite
    cout_fixe   : arbitrage kilometres / nombre de vehicules (D31)
    flotte      : courbe distance / taille de flotte (remplace D31)

Chaque campagne ecrit un CSV horodate dans resultats/. Les mesures du
rapport doivent etre tracables : la recherche est pilotee par le temps
mural, un CSV regenere ne redonnera pas exactement les memes chiffres
(ecart observe de l'ordre de 1 %).

Usage (depuis la racine du projet) :
    python -m scripts.calibrer temps
    python -m scripts.calibrer strategies --limite 60
    python -m scripts.calibrer penalite --limite 60
    python -m scripts.calibrer cout_fixe --limite 60
    python -m scripts.calibrer flotte --limite 60
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
from app.services.solveur import (
    COUT_FIXE_VEHICULE_M,
    PENALITE_ABANDON_M,
    resoudre,
)

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "resultats"

COLONNES = [
    "campagne", "horodatage", "limite_s", "penalite", "caissons",
    "cout_fixe",
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

    ATTENTION : cette garantie porte sur la PRESENCE d'un type, pas sur sa
    CAPACITE. Au J3, retirer les deux derniers vehicules laisse un seul
    refrigere de 16,00 m3 pour 16,20 m3 de lots refrigeres -- faisable au
    sens de la compatibilite, infaisable au sens du volume. D'ou
    reduire_et_controler() ci-dessous.

    Reserve J4 : les vehicules sont retenus par id_vehicule croissant,
    sans egard pour leur station de rattachement. Une fois la contrainte
    de source active, cette selection pourra vider un depot entier de ses
    vehicules et rendre infaisables tous les lots qui en partent. Il
    faudra alors garantir la couverture par depot, comme on garantit
    aujourd'hui celle par type de caisson.
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


def reduire_et_controler(ctx: ContexteSolveur, n: int) -> ContexteSolveur:
    """
    reduire_flotte() suivi de controler().

    Retirer des vehicules peut rendre le contexte structurellement
    infaisable -- typiquement quand le dernier vehicule d'un type de
    caisson emporte moins de volume que ne le demandent les lots de ce
    type. L'abandon qui en resulte est alors une consequence mecanique,
    pas un resultat d'optimisation : il doit etre annonce, pas decouvert
    apres coup.

    Les anomalies sont affichees, pas levees : une campagne doit aller au
    bout de sa serie, l'infaisabilite d'un point etant elle-meme une
    mesure (elle situe le seuil de rupture).
    """
    reduit = reduire_flotte(ctx, n)
    for a in controler(reduit):
        print(f"    ! flotte {n} : {a}")
    return reduit


# ---------------------------------------------------------------------------
# Mesure elementaire
# ---------------------------------------------------------------------------

def mesurer(ctx: ContexteSolveur, campagne: str, **kw) -> dict:
    """
    Une resolution, une ligne de CSV.

    Les parametres absents de kw sont traces a leur valeur par defaut et
    non laisses vides : un CSV relu dans six semaines doit dire sous quel
    reglage exact la mesure a ete prise.
    """
    t0 = time.perf_counter()
    res = resoudre(ctx, **kw)
    duree = time.perf_counter() - t0

    ligne = {
        "campagne": campagne,
        "horodatage": datetime.now().isoformat(timespec="seconds"),
        "limite_s": kw.get("limite_secondes", ""),
        "penalite": kw.get("penalite", PENALITE_ABANDON_M),
        "caissons": kw.get("caissons", True),
        "cout_fixe": kw.get("cout_fixe", COUT_FIXE_VEHICULE_M),
        "premiere_solution": kw.get("premiere_solution", ""),
        "metaheuristique": kw.get("metaheuristique", ""),
        "nb_vehicules": ctx.nb_vehicules,
        "statut": res.statut,
        "distance_km": round(res.distance_totale_m / 1000, 1),
        "vehicules_utilises": res.nb_vehicules_utilises,
        "lots_servis": len(ctx.lots) - len(res.lots_non_servis),
        "lots_non_servis": len(res.lots_non_servis),
        "ids_non_servis": " ".join(str(i) for i in res.ids_non_servis),
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

COUTS_FIXES = [0, 100_000, 200_000, 400_000, 600_000, 1_000_000]

FLOTTES = [11, 9, 8, 7, 6, 5]


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


def campagne_cout_fixe(ctx, limite: int) -> list[dict]:
    """
    Balayage du cout fixe par vehicule (D31).

    Deux lectures attendues : le nombre de vehicules doit decroitre quand
    le cout monte, et la distance croitre. Une non-monotonie signale que
    la recherche decroche plutot qu'elle n'arbitre.

    Resultat de la campagne : D31 invalidee. A nombre de vehicules
    constant (6 pour 200, 400, 600 et 1000 km), le cout fixe est un terme
    constant qui ne peut pas changer la solution optimale ; la distance
    passe pourtant de 5375 a 10266 km. Campagne conservee car c'est elle
    qui documente l'invalidation.

    La colonne a lire n'est pas distance_km seule mais
    distance_km + cout_fixe x vehicules_utilises : c'est l'objectif que
    le solveur minimise reellement.
    """
    lignes = []
    for cf in COUTS_FIXES:
        print(f"[cout_fixe] {cf // 1000} km par vehicule")
        lignes.append(mesurer(ctx, "cout_fixe", limite_secondes=limite,
                              caissons=True, cout_fixe=cf))
    return lignes


def campagne_flotte(ctx, limite: int) -> list[dict]:
    """
    Courbe distance / taille de flotte, sans cout fixe (D31 invalide).

    Le plafond est une contrainte, pas une penalite : il ne deforme pas
    l'objectif et la recherche ne decroche pas. Mesure J3 : la distance
    reste dans une bande de 7 % la ou le cout fixe la faisait varier d'un
    facteur 2,5.

    Lecture : seules les lignes a 120/120 lots servis sont comparables.
    En dessous, la distance BAISSE parce que des lots sont abandonnes,
    pas parce que la solution est meilleure.

    Resultat J3 : le solveur n'utilise que 7 vehicules sur 11, donc
    plafonner a 9 ou 8 ne contraint rien. Le point de rupture n'est pas
    le nombre de vehicules mais la capacite refrigeree -- voir
    reduire_et_controler().

    Reserve : reduire_flotte() retire les vehicules par id_vehicule sans
    tenir compte du depot. Valable tant que la source des lots n'est pas
    contrainte ; a reprendre au J4.
    """
    lignes = []
    for n in FLOTTES:
        print(f"[flotte] {n} vehicules disponibles")
        reduit = reduire_et_controler(ctx, n)
        lignes.append(mesurer(reduit, "flotte", limite_secondes=limite,
                              caissons=True, cout_fixe=0))
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

    Cout fixe neutralise (cout_fixe=0) : on mesure ici le seul arbitrage
    servir / abandonner. Avec un cout d'ouverture de vehicule, un abandon
    pourrait devenir rentable parce qu'il evite de sortir un camion, et
    non parce que la penalite est trop faible -- deux causes melangees.
    """
    lignes = []

    for n in (8, 6, 4, 3):
        print(f"[penalite] flotte reduite a {n} vehicules")
        reduit = reduire_et_controler(ctx, n)
        lignes.append(mesurer(reduit, "penalite", limite_secondes=limite,
                              caissons=False, cout_fixe=0))

    for pen in (5_000_000, 500_000, 50_000, 5_000):
        print(f"[penalite] flotte complete, penalite={pen} m")
        lignes.append(mesurer(ctx, "penalite", limite_secondes=limite,
                              penalite=pen, caissons=False, cout_fixe=0))

    return lignes


# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Calibration du solveur MDVRP")
    p.add_argument("campagne",
                   choices=["temps", "strategies", "penalite", "cout_fixe",
                            "flotte"])
    p.add_argument("--limite", type=int, default=60,
                   help="limite de temps des campagnes autres que 'temps'")
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
    elif args.campagne == "cout_fixe":
        lignes = campagne_cout_fixe(ctx, args.limite)
    elif args.campagne == "flotte":
        lignes = campagne_flotte(ctx, args.limite)
    else:
        lignes = campagne_penalite(ctx, args.limite)

    chemin = ecrire(args.campagne, lignes)
    print(f"\n{len(lignes)} mesures -> {chemin.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
