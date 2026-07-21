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
    # colonne d'arrivee : retour au depot le plus proche
    matrice_km[: n - 1, index_arrivee] = matrice_base[
        np.ix_(projection, range(NB_STATIONS))
    ].min(axis=1)
    # ligne d'arrivee : rien n'en sort
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
        ends=[index_arrivee] * len(vehicules),
        lots=lots,
        vehicules=vehicules,
        noeuds_base=noeuds_base,
        index_arrivee=index_arrivee,
        statut_matrice=statut,
    )


def controler(ctx: ContexteSolveur) -> list[str]:
    """Anomalies bloquantes ou suspectes. Liste vide = contexte sain."""
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

    # faisabilite par type de caisson (hypothese B : un caisson specialise
    # sert aussi le standard, jamais l'autre specialise)
    couverts = {
        "standard": {"standard"},
        "refrigere": {"standard", "refrigere"},
        "securise": {"standard", "securise"},
    }
    for besoin in {l.caisson_requis for l in ctx.lots}:
        charge = sum(l.volume_echelle for l in ctx.lots if l.caisson_requis == besoin)
        capa = sum(
            v.capacite_echelle
            for v in ctx.vehicules
            if besoin in couverts.get(v.type_caisson, set())
        )
        if charge > capa:
            a.append(
                f"caisson '{besoin}' infaisable : charge {charge/ECHELLE:.2f} "
                f"> capacite {capa/ECHELLE:.2f}"
            )

    if sum(ctx.demandes) > sum(ctx.capacites):
        a.append("charge totale superieure a la capacite totale")

    return a
