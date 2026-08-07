"""
Evaluateur d'affectation manuelle.

Renversement de logique par rapport au solveur MDVRP :
  - solveur.py DECIDE l'affectation (quel lot sur quel vehicule/depot) ;
  - evaluateur.py RECOIT une affectation figee par l'humain (couple
    chauffeur/vehicule + lots imposes) et ne la remet pas en cause.

Il fait deux choses, sans jamais bloquer ni ecrire en base :
  1. Controles -> violations NON bloquantes (capacite, caisson, source).
  2. Reordonnancement TSP par tournee : vehicule et lots figes, on n'optimise
     que l'ORDRE de visite (OR-Tools, un sous-probleme par tournee). Le
     vehicule repart de son depot et y revient.

Conventions reprises telles quelles (aucune reinvention) :
  - matrice routiere + plancher D13 via distances.matrice_pour_solveur ;
  - mapping entite -> index via distances.entite_vers_index ;
  - asymetrie D16 preservee (l'ordre i,j est significatif) ;
  - echelle volumes/capacites x ECHELLE ; distances en metres entiers (x1000),
    comme matrice_etendue ;
  - compatibilite caisson via solveur.couvre (source de verite).

Decisions de cadrage :
  - UN LOT = UN ARRET. L'evaluateur ne fractionne JAMAIS (l'humain impose) :
    un lot trop gros pour son vehicule devient une violation de capacite, pas
    un decoupage en parts. Pas de PartLot ici -- logique bien plus simple que
    le solveur.
  - PAS de dimension capacite contraignante dans le TSP : une tournee
    surchargee ne doit pas rendre le TSP infaisable (controles non bloquants).
    La capacite est rapportee, jamais un echec de resolution.
  - BINOME D12 non controle : un chauffeur different de l'attitre est accepte
    sans signalement.
  - COUVERTURE DE VAGUE : les lots de la vague absents de l'affectation sont
    signales 'non affectes' (info, non bloquant).
"""

from dataclasses import dataclass, field

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.models.lot import Lot
from app.models.vehicule import Vehicule
from app.services.distances import (
    entite_vers_index,
    matrice_pour_solveur,
    obtenir_matrice_routiere,
)
from app.services.matrice_etendue import ECHELLE, charger_lots
from app.services.solveur import couvre

# TSP par tournee : quelques noeuds seulement, resolution quasi instantanee.
# Une petite limite suffit largement. Parametres homogenes avec le solveur.
LIMITE_SECONDES_TSP = 2
PREMIERE_SOLUTION = "PATH_CHEAPEST_ARC"
METAHEURISTIQUE = "GUIDED_LOCAL_SEARCH"


# ---------------------------------------------------------------------------
# Entree : l'affectation dictee par l'humain
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TourneeImposee:
    """Une tournee dictee par l'humain : un couple chauffeur/vehicule et les
    lots qui lui sont affectes. L'ordre des lots est indifferent -- c'est
    justement ce que l'evaluateur recalcule."""
    id_chauffeur: int
    id_vehicule: int
    ids_lots: list[int]


# ---------------------------------------------------------------------------
# Sortie : evaluation par tournee + agregat
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Violation:
    """Un manquement constate, TOUJOURS non bloquant.

    type :
      - 'capacite' : charge de la tournee > capacite du vehicule. C'est un fait
        de tournee (pas d'un lot en particulier) -> id_lot vaut None.
      - 'caisson'  : le caisson du vehicule ne couvre pas l'exigence du lot.
      - 'source'   : le lot part d'un depot autre que celui du vehicule.
    """
    type: str
    message: str
    id_lot: int | None = None


@dataclass
class TourneeEvaluee:
    id_chauffeur: int
    id_vehicule: int
    id_station_depart: int
    # id_lot dans l'ordre de visite optimise. Le retour au depot (D34) est
    # implicite : il est compte dans distance_m mais n'apparait pas ici.
    ordre_lots: list[int]
    distance_m: int
    charge_echelle: int
    capacite_echelle: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def taux_charge(self) -> float:
        """Charge / capacite en pourcentage (0 si capacite nulle)."""
        if self.capacite_echelle <= 0:
            return 0.0
        return 100.0 * self.charge_echelle / self.capacite_echelle


@dataclass
class Evaluation:
    tournees: list[TourneeEvaluee]
    lots_non_affectes: list[int]     # lots de la vague absents de l'affectation
    distance_totale_m: int

    @property
    def nb_violations(self) -> int:
        return sum(len(t.violations) for t in self.tournees)


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------
def evaluer(db, id_vague: str,
            affectations: list[TourneeImposee]) -> Evaluation:
    """
    Evalue une affectation manuelle. LECTURE SEULE : ne touche jamais la base.

    Etapes :
      1. charge la matrice routiere (plancher) une seule fois ;
      2. pour chaque tournee imposee : controles + reordonnancement TSP ;
      3. couverture de vague : lots de la vague non affectes.
    """
    # matrice routiere brute -> plancher D13 (dormant). On ignore
    # le statut 'valide/perimee' ici : l'evaluateur n'est pas l'endroit pour
    # certifier la matrice (le solveur/controle s'en charge deja).
    matrice, _noeuds, _statut = obtenir_matrice_routiere(db)
    matrice = matrice_pour_solveur(matrice)

    tournees_evaluees: list[TourneeEvaluee] = []
    ids_affectes: list[int] = []

    for aff in affectations:
        vehicule = _charger_vehicule(db, aff.id_vehicule)
        lots = _charger_lots_ordonnes(db, aff.ids_lots)
        ids_affectes.extend(l.id_lot for l in lots)
        tournees_evaluees.append(
            _evaluer_tournee(matrice, vehicule, aff.id_chauffeur, lots)
        )

    # --- couverture de vague ---------------------------------------------
    # Les lots de la vague qui n'apparaissent dans aucune tournee sont
    # signales (info, non bloquant). set() absorbe d'eventuels doublons.
    affectes = set(ids_affectes)
    lots_vague = charger_lots(db, id_vague=id_vague)
    non_affectes = [l.id_lot for l in lots_vague if l.id_lot not in affectes]

    distance_totale = sum(t.distance_m for t in tournees_evaluees)
    return Evaluation(tournees_evaluees, non_affectes, distance_totale)


# ---------------------------------------------------------------------------
# Chargements (lecture seule, style db.query 1.x)
# ---------------------------------------------------------------------------
def _charger_vehicule(db, id_vehicule: int) -> Vehicule:
    v = db.query(Vehicule).filter(Vehicule.id_vehicule == id_vehicule).first()
    if v is None:
        raise ValueError(f"vehicule {id_vehicule} introuvable")
    return v


def _charger_lots_ordonnes(db, ids_lots: list[int]) -> list[Lot]:
    """Charge les lots par id, dans l'ordre fourni. Leve si un id manque."""
    if not ids_lots:
        return []
    trouves = {
        l.id_lot: l
        for l in db.query(Lot).filter(Lot.id_lot.in_(ids_lots)).all()
    }
    manquants = [i for i in ids_lots if i not in trouves]
    if manquants:
        raise ValueError(f"lot(s) introuvable(s) : {manquants}")
    return [trouves[i] for i in ids_lots]


# ---------------------------------------------------------------------------
# Evaluation d'une tournee : controles + reordonnancement
# ---------------------------------------------------------------------------
def _evaluer_tournee(matrice, vehicule, id_chauffeur: int,
                     lots: list[Lot]) -> TourneeEvaluee:
    capacite_echelle = int(round(float(vehicule.capacite) * ECHELLE))
    charge_echelle = sum(
        int(round(float(l.volume) * ECHELLE)) for l in lots
    )

    violations = _controler(vehicule, lots, charge_echelle, capacite_echelle)
    ordre, distance_m = _reordonner(matrice, vehicule, lots)

    return TourneeEvaluee(
        id_chauffeur=id_chauffeur,
        id_vehicule=vehicule.id_vehicule,
        id_station_depart=vehicule.id_station,
        ordre_lots=ordre,
        distance_m=distance_m,
        charge_echelle=charge_echelle,
        capacite_echelle=capacite_echelle,
        violations=violations,
    )


def _controler(vehicule, lots: list[Lot],
               charge_echelle: int, capacite_echelle: int) -> list[Violation]:
    """Les 3 familles de controle, toutes non bloquantes."""
    violations: list[Violation] = []

    # capacite : fait de tournee
    if charge_echelle > capacite_echelle:
        violations.append(Violation(
            type="capacite",
            message=(f"charge {charge_echelle / ECHELLE:.2f} > capacite "
                     f"{capacite_echelle / ECHELLE:.2f} m3"),
        ))

    for l in lots:
        # caisson : le vehicule couvre-t-il l'exigence du lot ? (solveur.couvre)
        if not couvre(vehicule.type_caisson, l.caisson_requis):
            violations.append(Violation(
                type="caisson",
                id_lot=l.id_lot,
                message=(f"caisson '{vehicule.type_caisson}' ne couvre pas "
                         f"l'exigence '{l.caisson_requis}'"),
            ))
        # source : le lot part-il du depot du vehicule ? (ignore si non renseigne)
        if l.id_station_source is not None \
                and l.id_station_source != vehicule.id_station:
            violations.append(Violation(
                type="source",
                id_lot=l.id_lot,
                message=(f"source depot {l.id_station_source} != depot vehicule "
                         f"{vehicule.id_station}"),
            ))

    return violations


def _reordonner(matrice, vehicule,
                lots: list[Lot]) -> tuple[list[int], int]:
    """
    Reordonne les arrets d'une tournee (vehicule et lots figes) par TSP.

    Noeud 0 = depot du vehicule (depart ET retour, D34). Noeuds 1..m = lots
    dans l'ordre fourni. On extrait la sous-matrice routiere correspondante
    (asymetrie D16 preservee), on la convertit en metres entiers (x1000) comme
    matrice_etendue, puis on resout un TSP a un seul vehicule -- sans aucune
    contrainte de capacite (celle-ci est un controle, pas un blocage).

    Renvoie (id_lot dans l'ordre de visite, distance totale en metres, retour
    depot inclus). Tournee vide -> ([], 0).
    """
    if not lots:
        return [], 0

    index_depot = entite_vers_index("station", vehicule.id_station)
    index_base = [index_depot] + [
        entite_vers_index("destination", l.id_destination) for l in lots
    ]

    # sous-matrice km -> metres entiers, comme le fait matrice_etendue.
    sous_km = matrice[np.ix_(index_base, index_base)]
    sous_m = np.rint(sous_km * 1000.0).astype(np.int64)

    # 1 seul vehicule ; depot unique = start ET end (D34).
    manager = pywrapcp.RoutingIndexManager(len(index_base), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def cout(i, j):
        return int(sous_m[manager.IndexToNode(i), manager.IndexToNode(j)])

    idx_cout = routing.RegisterTransitCallback(cout)
    routing.SetArcCostEvaluatorOfAllVehicles(idx_cout)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = getattr(
        routing_enums_pb2.FirstSolutionStrategy, PREMIERE_SOLUTION
    )
    params.local_search_metaheuristic = getattr(
        routing_enums_pb2.LocalSearchMetaheuristic, METAHEURISTIQUE
    )
    params.time_limit.FromSeconds(LIMITE_SECONDES_TSP)

    solution = routing.SolveWithParameters(params)
    if solution is None:
        # Un TSP a un vehicule sans contrainte ne devrait jamais echouer.
        # Repli defensif : ordre d'entree, distance non calculee.
        return [l.id_lot for l in lots], 0

    ordre: list[int] = []
    distance = 0
    index = routing.Start(0)
    while not routing.IsEnd(index):
        noeud = manager.IndexToNode(index)
        if noeud != 0:                       # 0 = depot, pas un lot
            ordre.append(lots[noeud - 1].id_lot)
        suivant = solution.Value(routing.NextVar(index))
        distance += routing.GetArcCostForVehicle(index, suivant, 0)
        index = suivant

    return ordre, distance


# ---------------------------------------------------------------------------
# Rendu console (tests en isolation, avant la couche API)
# ---------------------------------------------------------------------------
def resume(ev: Evaluation) -> str:
    lignes = [
        f"distance totale   : {ev.distance_totale_m / 1000:.1f} km",
        f"tournees          : {len(ev.tournees)}",
        f"violations        : {ev.nb_violations}",
        f"lots non affectes : {ev.lots_non_affectes or 'aucun'}",
        "",
    ]
    for t in ev.tournees:
        lignes.append(
            f"  veh {t.id_vehicule:2d} (chauf {t.id_chauffeur})  "
            f"depot {t.id_station_depart}  {len(t.ordre_lots):2d} arrets  "
            f"{t.distance_m / 1000:7.1f} km  charge {t.charge_echelle / ECHELLE:6.2f}"
            f" ({t.taux_charge:5.1f} %)"
        )
        lignes.append(f"     ordre : {t.ordre_lots}")
        for v in t.violations:
            cible = f" lot {v.id_lot}" if v.id_lot is not None else ""
            lignes.append(f"     [viol {v.type}{cible}] {v.message}")
    return "\n".join(lignes)
