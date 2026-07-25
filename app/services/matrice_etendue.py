"""
Construction du contexte d'entree du solveur OR-Tools (S5).

Etend la matrice canonique 105x105 (BF2) en une matrice 126x126 orientee
lot, seule forme exploitable par le solveur.

Convention d'index etendue (D27) :
    0   .. 4     stations (depots)        -- identique a distances.py
    5   .. 124   noeuds de livraison, UN PAR LOT, id_lot croissant
    125          noeud d'arrivee virtuel

Un noeud par lot et non par destination : 20 destinations portent deux lots,
dont les caissons requis peuvent differer. Agreger la demande par destination
fusionnerait des contraintes incompatibles.

Deux lots d'une meme destination sont des "jumeaux" : ils pointent vers le
meme index de base, leur distance mutuelle vaut 0 et doit le rester. C'est
pourquoi le plancher D13 est applique AVANT l'extension, sur la matrice de
base, ou les jumeaux relevent de la diagonale.

Noeud d'arrivee virtuel : tous les vehicules y terminent. Son cout d'entree
vaut min_k d(i, station_k) -- le solveur paie le retour au depot le plus
proche sans qu'on lui impose lequel. Rien n'en sort : d(125, .) = 0.
Le depot de retour reel se deduit apres resolution (id_station_retour, J4).

D26 : OR-Tools n'admet que des entiers dans une dimension de capacite.
Distances en metres entiers, volumes et capacites en centiemes.

S5 J4 : LotSolveur porte desormais id_station_source (contrainte de station
source, D33). controler() teste la faisabilite caisson DEPOT PAR DEPOT et non
plus seulement en agrege : la contrainte de source ayant decoupe le probleme
en cinq sous-problemes, une capacite globale suffisante ne garantit plus la
faisabilite locale.
"""

from dataclasses import dataclass

import numpy as np

from app.models.lot import Lot
from app.models.vehicule import Vehicule
from app.models.chauffeur import Chauffeur
from app.services.distances import (
    NB_STATIONS,
    Noeud,
    entite_vers_index,
    matrice_pour_solveur,
    obtenir_matrice_routiere,
)

# Facteur de mise a l'echelle des volumes et capacites (D26).
ECHELLE = 100

# Compatibilite caisson (hypothese B). Dupliquee depuis solveur.CAISSONS_COUVERTS
# a dessein : l'importer creerait un import circulaire, solveur important deja
# ce module. Source de verite : solveur.couvre.
_CAISSONS_COUVERTS: dict[str, set[str]] = {
    "standard": {"standard"},
    "refrigere": {"standard", "refrigere"},
    "securise": {"standard", "securise"},
}


@dataclass(frozen=True)
class LotSolveur:
    index: int          # index dans la matrice etendue
    id_lot: int
    id_destination: int
    index_base: int     # index de la destination dans la matrice 105x105
    caisson_requis: str
    volume_echelle: int
    priorite: str
    fragile: bool
    id_station_source: int | None   # depot d'appartenance (D33) ; None = non renseigne


@dataclass(frozen=True)
class VehiculeSolveur:
    rang: int           # position dans les listes OR-Tools (0 .. nb-1)
    id_vehicule: int
    id_station: int
    index_depart: int   # id_station - 1
    type_caisson: str
    capacite_echelle: int


@dataclass(frozen=True)
class ContexteSolveur:
    matrice: np.ndarray             # (n, n) entiers, metres
    demandes: list[int]             # (n) centiemes de volume
    capacites: list[int]            # (nb_vehicules) centiemes
    starts: list[int]
    ends: list[int]
    lots: list[LotSolveur]
    vehicules: list[VehiculeSolveur]
    noeuds_base: list[Noeud]
    index_arrivee: int
    statut_matrice: str             # 'valide' ou 'perimee'

    @property
    def nb_noeuds(self) -> int:
        return self.matrice.shape[0]

    @property
    def nb_vehicules(self) -> int:
        return len(self.vehicules)


def charger_lots(db) -> list[Lot]:
    """Tous les lots, tries par id_lot croissant (ordre canonique)."""
    return db.query(Lot).order_by(Lot.id_lot).all()


def charger_flotte(db) -> list[Vehicule]:
    """
    Flotte mobilisable (D23) : vehicule assure, appaire a un chauffeur,
    dont le chauffeur est actif. `vehicule.statut` n'est pas discriminant
    (tous a 'actif' dans le jeu courant).
    """
    return (
        db.query(Vehicule)
        .join(Chauffeur, Chauffeur.id_chauffeur == Vehicule.id_chauffeur)
        .filter(Vehicule.assurance == 1)
        .filter(Vehicule.id_chauffeur.isnot(None))
        .filter(Chauffeur.statut == "actif")
        .order_by(Vehicule.id_vehicule)
        .all()
    )


def construire_contexte(db) -> ContexteSolveur:
    """
    Assemble tout ce que le solveur consomme. Une seule lecture de la base.
    """
    matrice_base, noeuds_base, statut = obtenir_matrice_routiere(db)
    # Plancher D13 applique ICI, sur la base : les jumeaux relevent de la
    # diagonale et sont donc epargnes. Dormant depuis D14.
    matrice_base = matrice_pour_solveur(matrice_base)

    lots_bruts = charger_lots(db)
    flotte_brute = charger_flotte(db)
    if not lots_bruts:
        raise ValueError("Aucun lot a affecter.")
    if not flotte_brute:
        raise ValueError("Flotte mobilisable vide (D23).")

    nb_lots = len(lots_bruts)
    index_arrivee = NB_STATIONS + nb_lots
    n = index_arrivee + 1

    lots: list[LotSolveur] = []
    for rang, l in enumerate(lots_bruts):
        lots.append(
            LotSolveur(
                index=NB_STATIONS + rang,
                id_lot=l.id_lot,
                id_destination=l.id_destination,
                index_base=entite_vers_index("destination", l.id_destination),
                caisson_requis=l.caisson_requis,
                volume_echelle=int(round(float(l.volume) * ECHELLE)),
                priorite=l.priorite,
                fragile=bool(l.fragile),
                id_station_source=l.id_station_source,
            )
        )

    vehicules: list[VehiculeSolveur] = []
    for rang, v in enumerate(flotte_brute):
        vehicules.append(
            VehiculeSolveur(
                rang=rang,
                id_vehicule=v.id_vehicule,
                id_station=v.id_station,
                index_depart=v.id_station - 1,
                type_caisson=v.type_caisson,
                capacite_echelle=int(round(float(v.capacite) * ECHELLE)),
            )
        )

    # --- projection index etendu -> index de base -------------------------
    # Les stations se projettent sur elles-memes ; chaque lot sur sa
    # destination. Deux jumeaux partagent donc le meme index de base.
    projection = list(range(NB_STATIONS)) + [l.index_base for l in lots]

    # --- assemblage de la matrice ----------------------------------------
    sous = matrice_base[np.ix_(projection, projection)]        # (n-1, n-1) km

    matrice_km = np.zeros((n, n), dtype=float)
    matrice_km[: n - 1, : n - 1] = sous
    # Noeud d'arrivee virtuel (index_arrivee) : DEVENU INERTE au J4 (D34).
    #
    # Avant D34, tous les vehicules terminaient sur ce noeud unique, dont le
    # cout d'entree valait min_k d(i, station_k) : le retour au depot le plus
    # PROCHE. Neutre tant qu'un vehicule pouvait finir pres de n'importe quel
    # depot ; faux des que la contrainte de source impose a chaque vehicule de
    # rentrer a SON depot. Le vehicule securise du depot 1 livrant dans le sud
    # se voyait attribuer un retour vers le depot 5, sous-estimant la distance.
    #
    # D34 : ends pointe desormais sur le depot de depart de chaque vehicule
    # (voir ContexteSolveur ci-dessous). Le retour reel est alors paye dans la
    # matrice de base, qui code d(lot, depot) correctement. Le noeud virtuel
    # n'est plus une destination : on le rend inatteignable (cout d'entree
    # prohibitif) pour garantir qu'aucun vehicule ne l'emprunte, tout en
    # conservant la taille 126 et les invariants qui en dependent.
    #
    # Nettoyage possible (tache cosmetique) : retirer le noeud et passer en
    # 125x125. Non fait ici pour limiter la surface du correctif.
    PROHIBITIF_KM = 1e9
    matrice_km[: n - 1, index_arrivee] = PROHIBITIF_KM
    # ligne d'arrivee : rien n'en sort (invariant conserve, teste par controler)
    matrice_km[index_arrivee, :] = 0.0
    np.fill_diagonal(matrice_km, 0.0)

    matrice = np.rint(matrice_km * 1000.0).astype(np.int64)

    demandes = [0] * n
    for l in lots:
        demandes[l.index] = l.volume_echelle

    return ContexteSolveur(
        matrice=matrice,
        demandes=demandes,
        capacites=[v.capacite_echelle for v in vehicules],
        starts=[v.index_depart for v in vehicules],
        # D34 : chaque vehicule termine a SON depot de depart (start == end),
        # pas sur le noeud virtuel partage. OR-Tools accepte des ends partages
        # entre vehicules d'un meme depot et compte correctement le retour au
        # depot dans la distance (verifie). Corrige la sous-estimation de
        # distance et le id_station_retour incoherent sous contrainte de source.
        ends=[v.index_depart for v in vehicules],
        lots=lots,
        vehicules=vehicules,
        noeuds_base=noeuds_base,
        index_arrivee=index_arrivee,
        statut_matrice=statut,
    )


def controler(ctx: ContexteSolveur) -> list[str]:
    """
    Anomalies bloquantes ou suspectes. Liste vide = contexte sain.

    Les lignes prefixees '[info]' ne sont PAS bloquantes : elles signalent
    des lots que le solveur abandonnera proprement par disjonction (D28),
    resultat d'exploitation et non erreur de donnees. Les autres lignes sont
    des anomalies franches.
    """
    a: list[str] = []
    n = ctx.nb_noeuds

    if ctx.statut_matrice != "valide":
        a.append(f"matrice routiere '{ctx.statut_matrice}' : regenerer avant usage")
    if ctx.matrice.shape != (n, n):
        a.append(f"matrice non carree : {ctx.matrice.shape}")
    if not np.all(np.diag(ctx.matrice) == 0):
        a.append("diagonale non nulle")
    if np.any(ctx.matrice < 0):
        a.append("distance negative")
    if np.any(ctx.matrice[ctx.index_arrivee, :] != 0):
        a.append("le noeud d'arrivee n'est pas absorbant")

    # jumeaux : distance mutuelle strictement nulle attendue
    par_dest: dict[int, list[LotSolveur]] = {}
    for l in ctx.lots:
        par_dest.setdefault(l.id_destination, []).append(l)
    for id_dest, groupe in par_dest.items():
        if len(groupe) < 2:
            continue
        for i in range(len(groupe)):
            for j in range(len(groupe)):
                if i != j and ctx.matrice[groupe[i].index, groupe[j].index] != 0:
                    a.append(
                        f"jumeaux dest {id_dest} : distance non nulle entre "
                        f"lots {groupe[i].id_lot} et {groupe[j].id_lot}"
                    )

    # --- faisabilite caisson, DEPOT PAR DEPOT (S5 J4) ---------------------
    # Remplace l'ancien test agrege. La contrainte de source ayant decoupe le
    # probleme, une capacite globale suffisante ne garantit plus rien : un lot
    # refrigere au depot 2 ne peut etre servi que par un vehicule refrigere DU
    # DEPOT 2.
    #   - capacite locale insuffisante  -> anomalie bloquante
    #   - aucun porteur du tout au depot -> [info] : abandon par disjonction
    depots = sorted({
        l.id_station_source for l in ctx.lots if l.id_station_source is not None
    })
    non_renseignes = [l.id_lot for l in ctx.lots if l.id_station_source is None]
    if non_renseignes:
        apercu = ", ".join(str(i) for i in non_renseignes[:10])
        suite = " ..." if len(non_renseignes) > 10 else ""
        a.append(
            f"{len(non_renseignes)} lot(s) sans station source : {apercu}{suite} "
            f"— peupler id_station_source avant optimisation"
        )

    for depot in depots:
        lots_depot = [l for l in ctx.lots if l.id_station_source == depot]
        for besoin in {l.caisson_requis for l in lots_depot}:
            charge = sum(
                l.volume_echelle for l in lots_depot if l.caisson_requis == besoin
            )
            capa = sum(
                v.capacite_echelle
                for v in ctx.vehicules
                if v.id_station == depot
                and besoin in _CAISSONS_COUVERTS.get(v.type_caisson, set())
            )
            nb = sum(1 for l in lots_depot if l.caisson_requis == besoin)
            if capa == 0:
                a.append(
                    f"[info] depot {depot}, caisson '{besoin}' : aucun porteur "
                    f"({nb} lot(s), {charge/ECHELLE:.2f} m3) — abandon par disjonction"
                )
            elif charge > capa:
                a.append(
                    f"depot {depot}, caisson '{besoin}' infaisable : charge "
                    f"{charge/ECHELLE:.2f} > capacite locale {capa/ECHELLE:.2f}"
                )

    # garde-fou global conserve
    if sum(ctx.demandes) > sum(ctx.capacites):
        a.append("charge totale superieure a la capacite totale")

    return a
