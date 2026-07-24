"""
Solveur MDVRP (OR-Tools) -- S5 J2, calibre au J3, decoupe au J4.

Consomme le ContexteSolveur produit par matrice_etendue.construire_contexte()
et renvoie une solution exploitable : une tournee par vehicule, plus la liste
des lots non servis.

Perimetre : distance + capacite + disjonctions penalisees + caissons + source.

Disjonctions (D28) : chaque noeud de livraison est optionnel, moyennant une
penalite. Sans cela, la moindre insuffisance de capacite fait echouer la
resolution en renvoyant None, sans diagnostic. Avec, le solveur livre ce
qu'il peut et signale le reste -- comportement attendu d'un outil
d'exploitation.

Caissons (hypothese B) : chaque lot est restreint aux vehicules dont le
caisson couvre son exigence. La contrainte est debrayable (caissons=False)
afin de mesurer son surcout a budget de temps egal.

Station source (D33, S5 J4) : chaque lot n'est servable que par les vehicules
bases a son depot d'appartenance (lot.id_station_source). Fusionnee avec la
contrainte caisson dans le meme domaine de VehicleVar : le domaine autorise
est l'INTERSECTION des deux conditions. Cette contrainte decoupe de facto le
probleme en cinq sous-problemes independants -- aucune tournee ne franchit la
frontiere entre deux depots -- sans qu'il faille cinq resolutions distinctes.
Debrayable (source=False) pour retrouver le modele calibre au J3 et mesurer
le surcout du decoupage.

Cout fixe par vehicule (D31) : mecanisme conserve comme parametre mais
NEUTRALISE par defaut, la campagne de calibration ayant montre qu'il
degrade la recherche au lieu de l'orienter. Le pilotage du nombre de
vehicules passe par un plafond de flotte, qui est une contrainte et non
une penalite.

Calibration (J3) : limite de temps, penalite d'abandon, cout fixe et
strategie de recherche sont tous des parametres de resoudre(). Les valeurs
par defaut ci-dessous sont les valeurs de production, etablies par
scripts/calibrer.py ; les mesures correspondantes sont dans resultats/.
A REMESURER au J4 : le decoupage par source rend chaque sous-probleme plus
facile, la limite de 60 s est probablement trop genereuse.
"""

from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.services.distances import NB_STATIONS
from app.services.matrice_etendue import ContexteSolveur, ECHELLE

# Penalite d'abandon d'un lot, en metres. Doit depasser largement le plus
# long detour envisageable (max de la matrice ~755 km) pour que l'abandon
# reste un dernier recours et jamais une optimisation de confort.
#
# Validee au J3 : a flotte complete, 5 000 000 et 500 000 m servent les
# 120 lots ; 50 000 m en abandonne 39 et 5 000 m en abandonne 118. La
# bascule se situe donc entre 500 et 50 km, coherente avec un cout
# marginal moyen d'environ 25 km par lot. 500 000 m suffirait sur ce jeu
# de donnees mais reste SOUS le plus long trajet de la matrice : elle
# passerait par chance, pas par construction. 5 000 000 conserve un
# facteur 6,6 de marge.
PENALITE_ABANDON_M = 5_000_000

# Cout fixe d'une sortie de vehicule, en metres (D31) -- DESACTIVE.
#
# Mecanisme conserve comme parametre mais neutralise par defaut. La
# campagne cout_fixe montre qu'il degrade la recherche au lieu de la
# guider : a nombre de vehicules constant (6 pour 200, 400, 600 et
# 1000 km), le terme est une constante et ne devrait pas changer la
# solution optimale ; la distance passe pourtant de 5375 a 10266 km. La
# solution trouvee sans cout fixe reste meilleure sous tous les couts
# testes, l'ecart croissant avec la valeur.
#
# Remplace par un plafond de flotte (campagne "flotte"), qui est une
# contrainte et non une penalite.
COUT_FIXE_VEHICULE_M = 0

# 60 s. Le plateau reel est a 120 s, mais l'endpoint POST /optimisations
# du J5 est synchrone et 120 s depasse les delais d'expiration usuels des
# passerelles HTTP. On concede ces 5 % a la robustesse du service.
#
# A REMESURER au J4 : la contrainte de station source decoupe le probleme
# en cinq sous-problemes independants, nettement plus faciles.
LIMITE_SECONDES = 60

PREMIERE_SOLUTION = "PARALLEL_CHEAPEST_INSERTION"
METAHEURISTIQUE = "GUIDED_LOCAL_SEARCH"

# ---------------------------------------------------------------------------
# Compatibilite caisson (hypothese B, decision D-serie)
#
# Un caisson specialise sert aussi le standard (il est plus contraignant
# que necessaire, jamais moins). Deux specialises ne se servent pas
# mutuellement : un caisson refrigere n'offre aucune garantie de securite,
# et reciproquement.
# ---------------------------------------------------------------------------
CAISSONS_COUVERTS: dict[str, frozenset[str]] = {
    "standard": frozenset({"standard"}),
    "refrigere": frozenset({"standard", "refrigere"}),
    "securise": frozenset({"standard", "securise"}),
}


def couvre(type_vehicule: str, caisson_requis: str) -> bool:
    """Le caisson du vehicule satisfait-il l'exigence du lot ?"""
    return caisson_requis in CAISSONS_COUVERTS.get(type_vehicule, frozenset())


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
             caissons: bool = True,
             source: bool = True,
             cout_fixe: int = COUT_FIXE_VEHICULE_M,
             premiere_solution: str = PREMIERE_SOLUTION,
             metaheuristique: str = METAHEURISTIQUE,
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

    # --- cout fixe d'ouverture d'un vehicule (D31, desactive par defaut) ---
    if cout_fixe:
        routing.SetFixedCostOfAllVehicles(cout_fixe)

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

    # --- restriction des vehicules autorises par lot ----------------------
    # Caisson (hypothese B) et station source (D33) s'expriment tous deux
    # comme une restriction du domaine de VehicleVar. On les combine dans un
    # seul passage : le domaine autorise est l'intersection des conditions
    # actives. Chacune est debrayable pour la mesure.
    if caissons or source:
        _restreindre_vehicules(ctx, manager, routing,
                               caissons=caissons, source=source)

    # --- disjonctions : un lot peut rester non servi (D28) ----------------
    for lot in ctx.lots:
        routing.AddDisjunction([manager.NodeToIndex(lot.index)], penalite)

    # --- parametres de recherche -----------------------------------------
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = getattr(
        routing_enums_pb2.FirstSolutionStrategy, premiere_solution
    )
    params.local_search_metaheuristic = getattr(
        routing_enums_pb2.LocalSearchMetaheuristic, metaheuristique
    )
    params.time_limit.FromSeconds(limite_secondes)
    params.log_search = journal

    solution = routing.SolveWithParameters(params)
    if solution is None:
        return Resultat([], [l.id_lot for l in ctx.lots], 0, "echec")

    return _extraire(ctx, manager, routing, solution)


def _restreindre_vehicules(ctx: ContexteSolveur, manager, routing,
                           caissons: bool = True,
                           source: bool = True) -> dict[int, list[int]]:
    """
    Limite chaque lot aux vehicules autorises par les contraintes actives.

    Un vehicule est autorise pour un lot si TOUTES les conditions activees
    sont satisfaites :
      - caisson : couvre(v.type_caisson, lot.caisson_requis)
      - source  : v.id_station == lot.id_station_source

    Le rang du vehicule (v.rang) est l'identifiant attendu par OR-Tools :
    c'est la position dans les tableaux starts/ends passes au manager, pas
    l'id_vehicule de la base.

    Passe par VehicleVar().SetValues() plutot que par
    SetAllowedVehiclesForIndex() : le typemap SWIG de cette derniere est
    defaillant en ortools 9.15 (absl::Span<int const> non converti, quelle
    que soit la forme de la sequence Python passee).
    La valeur -1 doit figurer dans le domaine : c'est celle que prend la
    variable quand le noeud n'est visite par aucun vehicule. L'omettre
    rendrait la disjonction inoperante et ferait echouer la resolution sans
    diagnostic des la premiere infaisabilite.

    Doit etre appele avant SolveWithParameters ; apres, sans effet.

    Le dictionnaire renvoye n'est pas consomme par resoudre() ; il sert au
    diagnostic et aux tests (quels vehicules restent ouverts a quel lot).

    Lot sans vehicule autorise : le noeud est contraint a -1 (jamais visite),
    donc abandonne par disjonction. Depuis le decoupage par source (J4) ce
    cas est courant -- un lot refrigere partant d'un depot sans vehicule
    refrigere. On NE leve PLUS d'exception : controler() a deja signale ces
    lots en amont ('[info]'), et un abandon propre vaut mieux qu'une
    ValueError en pleine resolution dans un contexte web. Le domaine devient
    simplement [-1].
    """
    restrictions: dict[int, list[int]] = {}

    for lot in ctx.lots:
        autorises = []
        for v in ctx.vehicules:
            if caissons and not couvre(v.type_caisson, lot.caisson_requis):
                continue
            if source and lot.id_station_source is not None \
                    and v.id_station != lot.id_station_source:
                continue
            autorises.append(int(v.rang))

        idx = manager.NodeToIndex(lot.index)
        # -1 toujours present : autorise l'abandon. Si autorises est vide, le
        # domaine est [-1] et le lot est necessairement non servi.
        routing.VehicleVar(idx).SetValues(autorises + [-1])
        restrictions[lot.id_lot] = autorises

    return restrictions


def _extraire(ctx, manager, routing, solution) -> Resultat:
    """Traduit la solution OR-Tools en objets metier."""
    par_index = {l.index: l for l in ctx.lots}
    servis: set[int] = set()
    tournees: list[TourneeResultat] = []
    total = 0

    matrice = ctx.matrice

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

        # depot de retour : le plus proche du dernier point livre.
        retour = None
        if lots_tournee:
            candidats = [(int(matrice[dernier_noeud, s]), s)
                         for s in range(NB_STATIONS)]
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
