"""
Solveur MDVRP (OR-Tools) -- squelette S5 J1.

Consomme le ContexteSolveur produit par matrice_etendue.construire_contexte()
et renvoie une solution exploitable : une tournee par vehicule, plus la liste
des lots non servis.

Perimetre du J1 : distance + capacite + disjonctions penalisees.
Les contraintes de caisson (SetAllowedVehiclesForIndex, hypothese B) arrivent
au J2 ; en attendant, tout vehicule peut porter tout lot.

Disjonctions (D28) : chaque noeud de livraison est optionnel, moyennant une
penalite. Sans cela, la moindre insuffisance de capacite fait echouer la
resolution en renvoyant None, sans diagnostic. Avec, le solveur livre ce
qu'il peut et signale le reste -- comportement attendu d'un outil
d'exploitation.
"""

from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.services.matrice_etendue import ContexteSolveur, ECHELLE

# Penalite d'abandon d'un lot, en metres. Doit depasser largement le plus
# long detour envisageable (max de la matrice ~755 km) pour que l'abandon
# reste un dernier recours et jamais une optimisation de confort.
PENALITE_ABANDON_M = 5_000_000

LIMITE_SECONDES = 10


@dataclass
class TourneeResultat:
    rang_vehicule: int
    id_vehicule: int
    id_station_depart: int
    id_station_retour: int | None
    distance_m: int
    charge_echelle: int
    lots: list[int] = field(default_factory=list)   # id_lot dans l'ordre


@dataclass
class Resultat:
    tournees: list[TourneeResultat]
    lots_non_servis: list[int]
    distance_totale_m: int
    statut: str

    @property
    def nb_vehicules_utilises(self) -> int:
        return sum(1 for t in self.tournees if t.lots)


def resoudre(ctx: ContexteSolveur,
             limite_secondes: int = LIMITE_SECONDES,
             penalite: int = PENALITE_ABANDON_M,
             journal: bool = False) -> Resultat:

    manager = pywrapcp.RoutingIndexManager(
        ctx.nb_noeuds, ctx.nb_vehicules, ctx.starts, ctx.ends
    )
    routing = pywrapcp.RoutingModel(manager)

    # --- cout de deplacement ---------------------------------------------
    matrice = ctx.matrice

    def cout_arc(i, j):
        return int(matrice[manager.IndexToNode(i), manager.IndexToNode(j)])

    idx_cout = routing.RegisterTransitCallback(cout_arc)
    routing.SetArcCostEvaluatorOfAllVehicles(idx_cout)

    # --- dimension capacite ----------------------------------------------
    demandes = ctx.demandes

    def demande(i):
        return demandes[manager.IndexToNode(i)]

    idx_demande = routing.RegisterUnaryTransitCallback(demande)
    routing.AddDimensionWithVehicleCapacity(
        idx_demande,
        0,                      # pas de marge
        ctx.capacites,          # capacite par vehicule
        True,                   # cumul demarre a zero
        "Capacite",
    )

    # --- disjonctions : un lot peut rester non servi (D28) ----------------
    for lot in ctx.lots:
        routing.AddDisjunction([manager.NodeToIndex(lot.index)], penalite)

    # --- parametres de recherche -----------------------------------------
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.FromSeconds(limite_secondes)
    params.log_search = journal

    solution = routing.SolveWithParameters(params)
    if solution is None:
        return Resultat([], [l.id_lot for l in ctx.lots], 0, "echec")

    return _extraire(ctx, manager, routing, solution)


def _extraire(ctx, manager, routing, solution) -> Resultat:
    """Traduit la solution OR-Tools en objets metier."""
    par_index = {l.index: l for l in ctx.lots}
    servis: set[int] = set()
    tournees: list[TourneeResultat] = []
    total = 0

    # matrice de base pour deduire le depot de retour reel
    matrice = ctx.matrice
    nb_stations = len(set(ctx.starts)) if ctx.starts else 0

    for v in ctx.vehicules:
        index = routing.Start(v.rang)
        distance = 0
        charge = 0
        lots_tournee: list[int] = []
        dernier_noeud = manager.IndexToNode(index)

        while not routing.IsEnd(index):
            noeud = manager.IndexToNode(index)
            if noeud in par_index:
                lot = par_index[noeud]
                lots_tournee.append(lot.id_lot)
                servis.add(lot.id_lot)
                charge += lot.volume_echelle
                dernier_noeud = noeud
            suivant = solution.Value(routing.NextVar(index))
            distance += routing.GetArcCostForVehicle(index, suivant, v.rang)
            index = suivant

        # depot de retour : le plus proche du dernier point livre
        retour = None
        if lots_tournee:
            candidats = [(int(matrice[dernier_noeud, s]), s) for s in range(5)]
            retour = min(candidats)[1] + 1     # index -> id_station

        total += distance
        tournees.append(
            TourneeResultat(
                rang_vehicule=v.rang,
                id_vehicule=v.id_vehicule,
                id_station_depart=v.id_station,
                id_station_retour=retour,
                distance_m=distance,
                charge_echelle=charge,
                lots=lots_tournee,
            )
        )

    non_servis = [l.id_lot for l in ctx.lots if l.id_lot not in servis]
    return Resultat(tournees, non_servis, total, "resolu")


def resume(res: Resultat, ctx: ContexteSolveur) -> str:
    """Rendu console lisible."""
    lignes = [
        f"statut               : {res.statut}",
        f"distance totale      : {res.distance_totale_m / 1000:.1f} km",
        f"vehicules utilises   : {res.nb_vehicules_utilises} / {ctx.nb_vehicules}",
        f"lots servis          : {len(ctx.lots) - len(res.lots_non_servis)} / {len(ctx.lots)}",
        "",
    ]
    for t in res.tournees:
        if not t.lots:
            lignes.append(f"  veh {t.id_vehicule:2d}  (inutilise)")
            continue
        veh = next(v for v in ctx.vehicules if v.id_vehicule == t.id_vehicule)
        taux = 100 * t.charge_echelle / veh.capacite_echelle
        lignes.append(
            f"  veh {t.id_vehicule:2d}  station {t.id_station_depart} -> "
            f"{t.id_station_retour}  {len(t.lots):3d} lots  "
            f"{t.distance_m/1000:7.1f} km  charge {t.charge_echelle/ECHELLE:6.2f}"
            f" ({taux:5.1f} %)"
        )
    if res.lots_non_servis:
        lignes += ["", f"lots non servis : {res.lots_non_servis}"]
    return "\n".join(lignes)
