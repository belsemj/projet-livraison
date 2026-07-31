"""
Construction du contexte d'entree du solveur OR-Tools (S5 ; parts S7).

Etend la matrice canonique 105x105 (BF2) en une matrice orientee PART, seule
forme exploitable par le solveur.

Convention d'index etendue (D27, revisee S7) :
    0   .. 4          stations (depots)        -- identique a distances.py
    5   .. 5+P-1      noeuds de livraison, UNE PAR PART, dans l'ordre id_lot
    5+P              noeud d'arrivee virtuel
ou P est le nombre total de PARTS. Un lot qui tient dans un camion autorise de
son depot = 1 part (P augmente de 1) ; un lot trop gros = k parts (D-serie
fractionnement, S7). Avant le fractionnement, P == nombre de lots et la
convention se confond avec l'ancienne (index 5..124, arrivee 125).

--- Fractionnement CIBLE (S7) -------------------------------------------------
Un lot n'est decoupe QUE s'il ne tient dans AUCUN vehicule autorise de son
depot (meme id_station_source + caisson compatible). Dans ce cas :
    c_max = capacite du plus gros vehicule autorise
    k     = plafond(V / c_max)          # plus petit nombre de parts
    parts = k parts entieres, aussi egales que possible, sommant EXACTEMENT a V
Chaque part est un noeud independant cote capacite : le solveur peut donc les
poser sur des camions differents (c'est la capacite qui l'y force). Le
caractere "tout-ou-rien" (un lot livre en entier ou pas du tout) est impose
cote solveur en liant les etats de service des parts d'un meme lot -- il n'a
pas de trace ici : matrice_etendue se contente de produire les parts.

Q_min : abandonne (S7). Les parts egales ne produisent jamais de miettes, le
seuil minimal de S2 devient inutile.

--- Jumeaux ------------------------------------------------------------------
Deux noeuds d'une meme destination sont des "jumeaux" : meme index de base,
distance mutuelle nulle. Cela vaut desormais AUSSI pour les parts d'un meme
lot (meme destination). Le plancher D13 est applique AVANT l'extension, sur la
matrice de base, ou les jumeaux relevent de la diagonale.

--- Arrivee virtuelle (D34) --------------------------------------------------
Rendue inatteignable (cout d'entree prohibitif) : ends pointe sur les depots
de depart. Voir le bloc detaille dans construire_contexte.

D26 : OR-Tools n'admet que des entiers. Distances en metres entiers, volumes
et capacites en centiemes.
"""

import math
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


def _couvre(type_vehicule: str, caisson_requis: str) -> bool:
    """Miroir local de solveur.couvre (evite l'import circulaire)."""
    return caisson_requis in _CAISSONS_COUVERTS.get(type_vehicule, set())


@dataclass(frozen=True)
class PartLot:
    """Un noeud du solveur = une part d'un lot. Un lot non fractionne a une
    seule part portant tout son volume."""
    index: int              # index dans la matrice etendue
    volume_echelle: int     # volume de CETTE part (centiemes)


@dataclass(frozen=True)
class LotSolveur:
    id_lot: int
    id_destination: int
    index_base: int                 # index de la destination dans la matrice 105x105
    caisson_requis: str
    volume_echelle: int             # volume TOTAL du lot (somme des parts)
    priorite: str
    fragile: bool
    id_station_source: int | None   # depot d'appartenance (D33) ; None = non renseigne
    parts: tuple[PartLot, ...]      # 1 part si non fractionne, k sinon

    @property
    def indices(self) -> list[int]:
        """Index de tous les noeuds (parts) de ce lot."""
        return [p.index for p in self.parts]

    @property
    def est_fractionne(self) -> bool:
        return len(self.parts) > 1


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
    demandes: list[int]             # (n) centiemes de volume, par PART
    capacites: list[int]            # (nb_vehicules) centiemes
    starts: list[int]
    ends: list[int]
    lots: list[LotSolveur]          # unites METIER ; chaque lot porte ses parts
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

    @property
    def nb_parts(self) -> int:
        """Nombre total de noeuds de livraison (parts confondues)."""
        return sum(len(l.parts) for l in self.lots)


def charger_lots(db, id_vague: str | None = None) -> list[Lot]:
    """
    Lots a optimiser, tries par id_lot croissant (ordre canonique).

    id_vague None  -> tous les lots de la base (comportement historique :
                      le bouton "optimiser tous les lots").
    id_vague pose  -> uniquement les lots de cette vague (saisie front). Une
                      vague est un ensemble de commandes fige avant calcul ;
                      cf. Lot.id_vague. Plusieurs runs peuvent porter sur une
                      meme vague.
    """
    q = db.query(Lot)
    if id_vague is not None:
        q = q.filter(Lot.id_vague == id_vague)
    return q.order_by(Lot.id_lot).all()


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


def _capacite_max_autorisee(caisson_requis: str,
                            id_station_source: int | None,
                            vehicules: list[VehiculeSolveur]) -> int:
    """
    Capacite (echelle) du plus gros vehicule autorise pour un lot : meme depot
    source (si renseigne) ET caisson compatible. 0 si aucun vehicule autorise.
    """
    return max(
        (v.capacite_echelle for v in vehicules
         if _couvre(v.type_caisson, caisson_requis)
         and (id_station_source is None or v.id_station == id_station_source)),
        default=0,
    )


def _decouper_volume(volume_echelle: int, k: int) -> list[int]:
    """
    Decoupe un volume entier en k parts aussi egales que possible, dont la
    somme vaut EXACTEMENT volume_echelle (aucune perte d'arrondi). Les 'reste'
    premieres parts recoivent une unite de plus.
    """
    base, reste = divmod(volume_echelle, k)
    return [base + 1 if i < reste else base for i in range(k)]


def _parts_du_lot(volume_echelle: int, c_max_echelle: int,
                  index_depart: int) -> tuple[list[PartLot], int]:
    """
    Construit les parts d'un lot a partir de l'index de depart fourni.

    - c_max == 0 (aucun vehicule autorise)  -> 1 part (le lot sera abandonne
      proprement par le solveur ; le fractionner n'aurait aucun sens).
    - volume <= c_max (tient dans un camion) -> 1 part.
    - sinon (trop gros)                      -> k = plafond(V / c_max) parts.

    Renvoie (liste de PartLot, prochain index libre).
    """
    if c_max_echelle <= 0 or volume_echelle <= c_max_echelle:
        k = 1
    else:
        k = math.ceil(volume_echelle / c_max_echelle)

    parts: list[PartLot] = []
    idx = index_depart
    for vol_part in _decouper_volume(volume_echelle, k):
        parts.append(PartLot(index=idx, volume_echelle=vol_part))
        idx += 1
    return parts, idx


def construire_contexte(db, id_vague: str | None = None) -> ContexteSolveur:
    """
    Assemble tout ce que le solveur consomme. Une seule lecture de la base.

    id_vague restreint l'optimisation a une vague de lots (None = tous les
    lots de la base). La flotte n'est JAMAIS restreinte : une vague est servie
    par tout le parc mobilisable, la contrainte de source se chargeant du
    decoupage par depot.
    """
    matrice_base, noeuds_base, statut = obtenir_matrice_routiere(db)
    # Plancher D13 applique ICI, sur la base : les jumeaux relevent de la
    # diagonale et sont donc epargnes. Dormant depuis D14.
    matrice_base = matrice_pour_solveur(matrice_base)

    lots_bruts = charger_lots(db, id_vague=id_vague)
    flotte_brute = charger_flotte(db)
    if not lots_bruts:
        raise ValueError(
            "Aucun lot a affecter dans cette vague."
            if id_vague is not None else "Aucun lot a affecter."
        )
    if not flotte_brute:
        raise ValueError("Flotte mobilisable vide (D23).")

    # --- vehicules d'abord : leurs capacites decident du decoupage des lots ---
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

    # --- lots : un noeud par part ; fractionnement cible des lots trop gros ---
    lots: list[LotSolveur] = []
    idx = NB_STATIONS
    for l in lots_bruts:
        volume_echelle = int(round(float(l.volume) * ECHELLE))
        c_max = _capacite_max_autorisee(l.caisson_requis, l.id_station_source, vehicules)
        parts, idx = _parts_du_lot(volume_echelle, c_max, idx)

        lots.append(
            LotSolveur(
                id_lot=l.id_lot,
                id_destination=l.id_destination,
                index_base=entite_vers_index("destination", l.id_destination),
                caisson_requis=l.caisson_requis,
                volume_echelle=volume_echelle,
                priorite=l.priorite,
                fragile=bool(l.fragile),
                id_station_source=l.id_station_source,
                parts=tuple(parts),
            )
        )

    total_parts = idx - NB_STATIONS
    index_arrivee = idx              # = NB_STATIONS + total_parts
    n = index_arrivee + 1

    # --- projection index etendu -> index de base -------------------------
    # Les stations se projettent sur elles-memes ; chaque PART sur la
    # destination de son lot. Toutes les parts d'un lot (et les jumeaux d'une
    # meme destination) partagent donc le meme index de base -> distance nulle.
    projection = list(range(NB_STATIONS))
    for lot in lots:
        projection.extend(lot.index_base for _ in lot.parts)

    # --- assemblage de la matrice ----------------------------------------
    sous = matrice_base[np.ix_(projection, projection)]        # (n-1, n-1) km

    matrice_km = np.zeros((n, n), dtype=float)
    matrice_km[: n - 1, : n - 1] = sous
    # Noeud d'arrivee virtuel (index_arrivee) : INERTE depuis le J4 (D34).
    #
    # ends pointe sur le depot de depart de chaque vehicule ; le noeud virtuel
    # n'est plus une fin de tournee. On le rend inatteignable (cout d'entree
    # prohibitif) pour qu'aucun vehicule ne l'emprunte, tout en conservant sa
    # presence dans le modele. Le solveur le laisse de cote via une disjonction
    # a penalite nulle (posee cote solveur).
    PROHIBITIF_KM = 1e9
    matrice_km[: n - 1, index_arrivee] = PROHIBITIF_KM
    # ligne d'arrivee : rien n'en sort (invariant conserve, teste par controler)
    matrice_km[index_arrivee, :] = 0.0
    np.fill_diagonal(matrice_km, 0.0)

    matrice = np.rint(matrice_km * 1000.0).astype(np.int64)

    # --- demande par PART -------------------------------------------------
    demandes = [0] * n
    for lot in lots:
        for p in lot.parts:
            demandes[p.index] = p.volume_echelle

    return ContexteSolveur(
        matrice=matrice,
        demandes=demandes,
        capacites=[v.capacite_echelle for v in vehicules],
        starts=[v.index_depart for v in vehicules],
        # D34 : chaque vehicule termine a SON depot de depart (start == end).
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

    # jumeaux ET parts : tous les noeuds d'une meme destination doivent avoir
    # une distance mutuelle nulle (parts d'un meme lot incluses).
    par_dest: dict[int, list[int]] = {}
    for lot in ctx.lots:
        for p in lot.parts:
            par_dest.setdefault(lot.id_destination, []).append(p.index)
    for id_dest, indices in par_dest.items():
        if len(indices) < 2:
            continue
        for i in range(len(indices)):
            for j in range(len(indices)):
                if i != j and ctx.matrice[indices[i], indices[j]] != 0:
                    a.append(
                        f"dest {id_dest} : distance non nulle entre noeuds "
                        f"{indices[i]} et {indices[j]} (jumeaux/parts)"
                    )

    # --- faisabilite caisson, DEPOT PAR DEPOT (S5 J4) ---------------------
    # Raisonne sur le volume TOTAL des lots (les parts n'y changent rien :
    # somme des parts == volume du lot). La contrainte de source ayant decoupe
    # le probleme, une capacite globale suffisante ne garantit plus rien.
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
                # Capacite locale insuffisante : des porteurs du bon caisson
                # existent, mais leur capacite cumulee au depot ne couvre pas
                # toute la charge. Le solveur en servira autant qu'il peut et
                # lachera le surplus par disjonction (raison capacite_locale au
                # niveau lot). NON bloquant : c'est un resultat d'exploitation,
                # pas une erreur de donnees -> plus de 409 (S7 J3).
                a.append(
                    f"[info] depot {depot}, caisson '{besoin}' : charge locale "
                    f"{charge/ECHELLE:.2f} > capacite {capa/ECHELLE:.2f} m3 — "
                    f"surplus abandonne par disjonction (capacite_locale)"
                )

    # Garde-fou global : la demande totale depasse la capacite totale de la
    # flotte. Meme logique que la capacite locale (S7 J3) : le solveur lachera
    # le surplus par disjonction (capacite_locale au niveau lot). NON bloquant
    # -> reste un diagnostic dans 'avertissements', jamais un 409.
    if sum(ctx.demandes) > sum(ctx.capacites):
        a.append(
            "[info] charge totale > capacite totale de la flotte — "
            "surplus abandonne par disjonction (capacite_locale)"
        )

    return a
