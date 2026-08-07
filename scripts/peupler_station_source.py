"""
Peuplement de id_station_source et id_vague sur les lots existants.

ECRIT EN BASE. Sauvegarde `livraison.db` avant modification.

Regle de rattachement :
  - standard, refrigere : depot le plus proche de la destination, lu dans le
    sens ALLER matrice[depot][destination] (matrice BRUTE, sans plancher D13,
    pour eviter les ex aequo artificiels sous 3 km).
  - securise : consolide au depot 1, seul a heberger le vehicule securise.
    Faute de quoi il faudrait modeliser des noeuds de ramassage (autre classe
    de probleme). C'est la traduction "donnees" de "un seul porteur securise
    pour tout le territoire".

id_vague : tous les lots existants recoivent 'vague_0'. Deja pose par le
server_default de la migration ; on le reaffirme ici par idempotence.

Invocation (depuis la racine du projet) :
    python -m scripts.peupler_station_source           # simulation
    python -m scripts.peupler_station_source --ecrire  # applique
"""

import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.services.distances import (
    NB_STATIONS,
    entite_vers_index,
    obtenir_matrice_routiere,
)
from app.services.matrice_etendue import charger_lots
from app.models.lot import Lot

DEPOT_SECURISE = 1          # depot hebergeant l'unique vehicule securise (D33)
VAGUE_INITIALE = "vague_0"
CHEMIN_BASE = Path("livraison.db")


def ouvrir_session():
    erreurs = []
    for module, fabrique in [
        ("app.database", "SessionLocal"),
        ("app.db.session", "SessionLocal"),
        ("app.db", "SessionLocal"),
        ("app.core.database", "SessionLocal"),
    ]:
        try:
            mod = __import__(module, fromlist=[fabrique])
            return getattr(mod, fabrique)()
        except (ImportError, AttributeError) as exc:
            erreurs.append(f"  {module}.{fabrique} : {exc}")
    raise SystemExit("Impossible d'ouvrir une session.\n" + "\n".join(erreurs))


def ligne(largeur: int = 74) -> None:
    print("-" * largeur)


def depot_proximite(id_destination: int, matrice) -> int:
    """Depot minimisant la distance ALLER vers la destination."""
    idx_dest = entite_vers_index("destination", id_destination)
    aller = {
        s: float(matrice[entite_vers_index("station", s)][idx_dest])
        for s in range(1, NB_STATIONS + 1)
    }
    return min(aller, key=aller.get)


def rattachement_cible(lot, matrice) -> int:
    """Depot source d'un lot selon la regle D33."""
    if lot.caisson_requis == "securise":
        return DEPOT_SECURISE
    return depot_proximite(lot.id_destination, matrice)


def main() -> None:
    ecrire = "--ecrire" in sys.argv

    db = ouvrir_session()
    try:
        matrice, _, statut = obtenir_matrice_routiere(db)
        lots = charger_lots(db)
    finally:
        db.close()

    print()
    ligne()
    print("PEUPLEMENT station source + vague")
    print("MODE SIMULATION (aucune ecriture)" if not ecrire else "MODE ECRITURE")
    ligne()
    print(f"Matrice : statut '{statut}'   Lots : {len(lots)}")

    if statut != "valide":
        raise SystemExit(
            "Matrice perimee : rattachement non fiable. Regenere avant."
        )

    # --- Calcul des cibles --------------------------------------------------
    cibles = {lot.id_lot: rattachement_cible(lot, matrice) for lot in lots}

    par_depot = defaultdict(lambda: defaultdict(list))
    for lot in lots:
        par_depot[cibles[lot.id_lot]][lot.caisson_requis].append(lot)

    print()
    ligne()
    print("REPARTITION CIBLE PAR DEPOT ET CAISSON")
    ligne()
    for s in range(1, NB_STATIONS + 1):
        contenu = par_depot.get(s, {})
        if not contenu:
            print(f"Depot {s} : —")
            continue
        detail = ", ".join(
            f"{len(contenu[c])} {c}" for c in sorted(contenu)
        )
        total = sum(len(v) for v in contenu.values())
        print(f"Depot {s} : {total} lot(s)  ({detail})")

    # --- Focus securise : la consolidation ----------------------------------
    securises = [lot for lot in lots if lot.caisson_requis == "securise"]
    print()
    ligne()
    print(f"CONSOLIDATION SECURISE — {len(securises)} lot(s) vers depot "
          f"{DEPOT_SECURISE}")
    ligne()
    for lot in securises:
        proche = depot_proximite(lot.id_destination, matrice)
        deplace = "" if proche == DEPOT_SECURISE else \
            f"  (proximite : depot {proche}, consolide)"
        print(f"  lot {lot.id_lot:<4} dest {lot.id_destination:<4}{deplace}")

    # --- Modifications a appliquer ------------------------------------------
    changements = [
        lot for lot in lots
        if lot.id_station_source != cibles[lot.id_lot]
        or lot.id_vague != VAGUE_INITIALE
    ]
    print()
    ligne()
    print(f"{len(changements)} lot(s) a mettre a jour sur {len(lots)}")
    ligne()

    if not ecrire:
        print("Simulation terminee. Rien n'a ete ecrit.")
        print("Relance avec --ecrire pour appliquer.")
        return

    # --- Sauvegarde ---------------------------------------------------------
    if not CHEMIN_BASE.exists():
        raise SystemExit(f"Base introuvable a '{CHEMIN_BASE}'.")
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauvegarde = CHEMIN_BASE.with_suffix(f".db.{horodatage}.bak")
    shutil.copy2(CHEMIN_BASE, sauvegarde)
    print(f"Sauvegarde : {sauvegarde}")

    # --- Ecriture -----------------------------------------------------------
    db = ouvrir_session()
    try:
        for lot in db.query(Lot).all():
            lot.id_station_source = cibles[lot.id_lot]
            lot.id_vague = VAGUE_INITIALE
        db.commit()
    finally:
        db.close()
    print("Ecriture effectuee.")

    # --- Verification sur session neuve -------------------------------------
    db2 = ouvrir_session()
    try:
        relu = charger_lots(db2)
    finally:
        db2.close()

    print()
    ligne()
    print("VERIFICATION")
    ligne()
    sans_source = [l.id_lot for l in relu if l.id_station_source is None]
    mauvaise_vague = [l.id_lot for l in relu if l.id_vague != VAGUE_INITIALE]
    ecarts = [l.id_lot for l in relu
              if l.id_station_source != cibles[l.id_lot]]

    if not sans_source and not mauvaise_vague and not ecarts:
        print(f"Les {len(relu)} lots ont une station source conforme et "
              f"id_vague = '{VAGUE_INITIALE}'.")
        repartition = defaultdict(int)
        for l in relu:
            repartition[l.id_station_source] += 1
        print("Repartition finale : " + ", ".join(
            f"depot {s} = {repartition[s]}" for s in sorted(repartition)
        ))
        print()
        print("Prochaine etape : contrainte de station source dans le solveur")
        print("(intersection avec la liste caisson), puis reprise de controler().")
    else:
        print("ECART detecte — restaure la sauvegarde et previens-moi.")
        if sans_source:
            print(f"  station source NULL : {sans_source}")
        if mauvaise_vague:
            print(f"  vague incorrecte : {mauvaise_vague}")
        if ecarts:
            print(f"  station != cible : {ecarts}")


if __name__ == "__main__":
    main()
