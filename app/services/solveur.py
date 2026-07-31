"""
Solveur MDVRP (OR-Tools) -- S5 J2, calibre au J3, decoupe au J4, parts au S7.

Consomme le ContexteSolveur produit par matrice_etendue.construire_contexte()
et renvoie une solution exploitable : une tournee par vehicule, plus la liste
des lots non servis.

Perimetre : distance + capacite + disjonctions penalisees + caissons + source
+ fractionnement (tout-ou-rien).

Disjonctions (D28) : chaque noeud de livraison est optionnel, moyennant une
penalite. Sans cela, la moindre insuffisance de capacite fait echouer la
resolution en renvoyant None, sans diagnostic. Avec, le solveur livre ce
qu'il peut et signale le reste -- comportement attendu d'un outil
d'exploitation.

Parts / fractionnement (S7) : un lot trop gros pour tout vehicule autorise de
son depot est decoupe en PARTS par matrice_etendue (chaque part est un noeud).
Ici, deux consequences :
  - la restriction caisson/source s'applique a CHAQUE part (memes regles) ;
  - le TOUT-OU-RIEN est impose en liant les ActiveVar des parts d'un meme lot :
    soit toutes livrees, soit toutes abandonnees, jamais un demi-lot. La
    penalite d'abandon est mutualisee sur les parts.
Un lot non fractionne a une seule part : le comportement est identique a avant.

Caissons (hypothese B) : chaque lot est restreint aux vehicules dont le
caisson couvre son exigence. La contrainte est debrayable (caissons=False)
afin de mesurer son surcout a budget de temps egal.

Station source (D33, S5 J4) : chaque lot n'est servable que par les vehicules
bases a son depot d'appartenance (lot.id_station_source). Fusionnee avec la
contrainte caisson dans le meme domaine de VehicleVar : le domaine autorise
est l'INTERSECTION des deux conditions. Debrayable (source=False).

Cout fixe par vehicule (D31) : mecanisme conserve comme parametre mais
NEUTRALISE par defaut (degrade la recherche au lieu de l'orienter).

Calibration (J3, recalibree S6 J1) : limite de temps, penalite d'abandon,
cout fixe et strategie de recherche sont des parametres de resoudre(). Les
valeurs par defaut sont les valeurs de production. A revalider apres l'ajout
des parts (S7), meme si l'impact est marginal : le fractionnement cible
n'ajoute des noeuds que pour les rares lots trop gros.
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
#
# S7 : pour un lot fractionne en k parts, cette penalite est repartie a
# raison de penalite // k par part. Abandonner le lot (toutes parts liees)
# coute donc ~penalite au total, pas k * penalite -- la comparaison avec le
# cout de livraison reste calibree comme avant.
PENALITE_ABANDON_M = 5_000_000

# Cout fixe d'une sortie de vehicule, en metres (D31) -- DESACTIVE.
COUT_FIXE_VEHICULE_M = 0

# 45 s. Recalibree au S6 J1 sur le probleme DECOMPOSE (contrainte de source,
# S5 J4). Le balayage 5-60 s montre un plateau a 30 s : 4446,5 km, inchange
# jusqu'a 60 s. On retient 45 s -- 50 % de marge au-dessus du plateau observe.
# La borne de requete (le=120) permet d'ajuster a la hausse sans redeploiement.
#
# Reserve : recalibrage mesure sous uvicorn sans --reload. A refaire apres
# l'ajout des parts (S7) si le nombre de lots trop gros devient significatif.
LIMITE_SECONDES = 45

PREMIERE_SOLUTION = "PARALLEL_CHEAPEST_INSERTION"
METAHEURISTIQUE = "GUIDED_LOCAL_SEARCH"

# Cout d'entree du noeud d'arrivee virtuel, rendu inatteignable au J4 (D34).
# Doit correspondre au PROHIBITIF_KM pose dans matrice_etendue (1e9 km), une
# fois converti en metres entiers par la matrice (x1000). Sert de seuil pour
# exclure de la distance affichee un eventuel arc vers ce noeud.
PROHIBITIF_M = 1e11

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
    # (id_lot, quantite_echelle) dans l'ordre de visite. Un lot fractionne
    # apparait par ses parts : une entree par part visitee. Un lot livre en
    # entier par un seul vehicule = une entree portant tout son volume.
    arrets: list[tuple[int, int]] = field(default_factory=list)

    @property
    def lots(self) -> list[int]:
        """Retro-compat (resume, scripts) : id_lot dans l'ordre de visite."""
        return [id_lot for id_lot, _ in self.arrets]


@dataclass
class Resultat:
    tournees: list[TourneeResultat]
    lots_non_servis: list[int]
    distance_totale_m: int
    statut: str

    @property
    def nb_vehicules_utilises(self) -> int:
        return sum(1 for t in self.tournees if t.arrets)


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

    # --- restriction des vehicules autorises par PART ---------------------
    # Caisson (hypothese B) et station source (D33) restreignent le domaine de
    # VehicleVar. On les combine dans un seul passage ; la restriction d'un lot
    # s'applique identiquement a chacune de ses parts. Chacune debrayable.
    if caissons or source:
        _restreindre_vehicules(ctx, manager, routing,
                               caissons=caissons, source=source)

    # --- disjonctions + tout-ou-rien par lot (D28 ; parts S7) -------------
    # Chaque PART est optionnelle (droppable) moyennant une part de penalite.
    # Pour un lot (fractionne ou non), on lie les ActiveVar de ses parts : le
    # solveur les sert TOUTES ou n'en sert AUCUNE -- jamais un demi-lot. La
    # penalite d'abandon est mutualisee (penalite // k par part).
    cp = routing.solver()
    for lot in ctx.lots:
        indices = [manager.NodeToIndex(p.index) for p in lot.parts]
        k = len(indices)
        part_penalite = penalite // k
        for idx in indices:
            routing.AddDisjunction([idx], part_penalite)
        # tout-ou-rien : etats de service lies (une part servie <=> toutes)
        for idx in indices[1:]:
            cp.Add(routing.ActiveVar(idx) == routing.ActiveVar(indices[0]))

    # --- noeud d'arrivee virtuel rendu optionnel gratuit (D34) -------------
    # Il reste present (taille du modele conservee) avec une ligne sortante
    # nulle. Une disjonction a penalite NULLE l'autorise a ne jamais etre
    # visite sans cout : le solveur le laisse systematiquement de cote.
    routing.AddDisjunction([manager.NodeToIndex(ctx.index_arrivee)], 0)

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
    Limite chaque PART aux vehicules autorises par les contraintes actives.

    Un vehicule est autorise pour un lot (donc pour chacune de ses parts) si
    TOUTES les conditions activees sont satisfaites :
      - caisson : couvre(v.type_caisson, lot.caisson_requis)
      - source  : v.id_station == lot.id_station_source

    Le rang du vehicule (v.rang) est l'identifiant attendu par OR-Tools : la
    position dans les tableaux starts/ends, pas l'id_vehicule de la base.

    Passe par VehicleVar().SetValues() plutot que SetAllowedVehiclesForIndex()
    (typemap SWIG defaillant en ortools 9.15). La valeur -1 doit figurer dans
    le domaine : c'est celle prise quand le noeud n'est visite par aucun
    vehicule ; l'omettre rendrait la disjonction inoperante.

    Part sans vehicule autorise : domaine [-1], donc jamais visitee -> le lot
    (toutes parts liees) est abandonne par disjonction. On NE leve PLUS
    d'exception : controler() a deja signale ces lots ('[info]'), et un abandon
    propre vaut mieux qu'une ValueError en plein solve dans un contexte web.

    Le dictionnaire renvoye (id_lot -> vehicules autorises) sert au diagnostic
    et aux tests. Les parts d'un lot partagent le meme domaine autorise.
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

        # meme domaine autorise applique a chaque part du lot
        for p in lot.parts:
            idx = manager.NodeToIndex(p.index)
            routing.VehicleVar(idx).SetValues(autorises + [-1])

        restrictions[lot.id_lot] = autorises

    return restrictions


def _extraire(ctx, manager, routing, solution) -> Resultat:
    """Traduit la solution OR-Tools en objets metier (niveau part)."""
    # index de part -> (lot, part)
    part_par_index: dict[int, tuple] = {}
    for lot in ctx.lots:
        for p in lot.parts:
            part_par_index[p.index] = (lot, p)

    parts_servies: set[int] = set()
    tournees: list[TourneeResultat] = []
    total = 0

    for v in ctx.vehicules:
        index = routing.Start(v.rang)
        distance = 0
        charge = 0
        arrets: list[tuple[int, int]] = []

        while not routing.IsEnd(index):
            noeud = manager.IndexToNode(index)
            if noeud in part_par_index:
                lot, part = part_par_index[noeud]
                arrets.append((lot.id_lot, part.volume_echelle))
                parts_servies.add(part.index)
                charge += part.volume_echelle
            suivant = solution.Value(routing.NextVar(index))
            cout_arc = routing.GetArcCostForVehicle(index, suivant, v.rang)
            # Garde-fou D34 : le noeud virtuel est inatteignable. Un arc
            # prohibitif signalerait qu'il a ete emprunte -- on l'exclut de la
            # somme pour ne pas faire exploser la distance affichee.
            if cout_arc < PROHIBITIF_M:
                distance += cout_arc
            index = suivant

        # D34 : le vehicule termine a SON depot de depart.
        retour = v.id_station if arrets else None

        total += distance
        tournees.append(
            TourneeResultat(
                rang_vehicule=v.rang,
                id_vehicule=v.id_vehicule,
                id_station_depart=v.id_station,
                id_station_retour=retour,
                distance_m=distance,
                charge_echelle=charge,
                arrets=arrets,
            )
        )

    # Un lot est servi SSI toutes ses parts le sont. Le tout-ou-rien le
    # garantit deja (toutes ou aucune), mais on le verifie sans le supposer.
    non_servis = [
        lot.id_lot for lot in ctx.lots
        if not all(p.index in parts_servies for p in lot.parts)
    ]
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
        if not t.arrets:
            lignes.append(f"  veh {t.id_vehicule:2d}  (inutilise)")
            continue
        veh = next(v for v in ctx.vehicules if v.id_vehicule == t.id_vehicule)
        taux = 100 * t.charge_echelle / veh.capacite_echelle
        lignes.append(
            f"  veh {t.id_vehicule:2d}  station {t.id_station_depart} -> "
            f"{t.id_station_retour}  {len(t.arrets):3d} arrets  "
            f"{t.distance_m/1000:7.1f} km  charge {t.charge_echelle/ECHELLE:6.2f}"
            f" ({taux:5.1f} %)"
        )
    if res.lots_non_servis:
        lignes += ["", f"lots non servis : {res.lots_non_servis}"]
    return "\n".join(lignes)
