"""
Diagnostic de l'affectation des lots a une station source (S5 J4).

LECTURE SEULE : aucune ecriture en base, aucun fichier produit.

Objet : simuler la regle "chaque lot part du depot le plus proche de sa
destination" et mesurer ce qu'elle implique AVANT de figer la migration.

Trois questions auxquelles ce script repond :
  1. Comment les 120 lots se repartissent-ils sur les 5 depots ?
  2. Une fois rattaches, quels lots n'ont plus aucun vehicule capable de les
     servir (caisson incompatible ou absent du depot) ?
  3. La capacite disponible par depot couvre-t-elle le volume rattache ?

Point de vigilance : la matrice routiere est ASYMETRIQUE. Le rattachement se
lit dans le sens ALLER, matrice[station][destination]. Le script mesure aussi
ce que donnerait le sens retour, pour chiffrer l'ecart.

La matrice est lue BRUTE, sans le plancher D13 : le plancher ecrase les
distances sous 3 km et creerait des ex aequo artificiels dans un classement.

Invocation (depuis la racine du projet) :
    python -m scripts.diag_station_source
"""

from collections import defaultdict

from app.services.distances import (
    NB_STATIONS,
    entite_vers_index,
    obtenir_matrice_routiere,
)
from app.services.matrice_etendue import charger_lots, charger_flotte

try:
    from app.services.solveur import couvre
except ImportError:  # pragma: no cover
    raise SystemExit(
        "Import de `couvre` impossible depuis app.services.solveur.\n"
        "Donne-moi le nom exact de l'aide de couverture des caissons "
        "(hypothese B) et je corrige le script."
    )


# ---------------------------------------------------------------------------
# Resolution tolerante des noms d'attributs
# ---------------------------------------------------------------------------

def _attribut(objet, candidats: list[str], etiquette: str):
    """Renvoie la valeur du premier attribut trouve parmi `candidats`."""
    for nom in candidats:
        if hasattr(objet, nom):
            return getattr(objet, nom)
    raise SystemExit(
        f"Attribut {etiquette} introuvable sur {type(objet).__name__} "
        f"(essayes : {', '.join(candidats)}). Corrige la liste en tete de script."
    )


def volume_de(lot) -> float:
    return float(_attribut(lot, ["volume", "volume_m3", "volume_total"], "volume"))


def capacite_de(vehicule) -> float:
    return float(_attribut(
        vehicule, ["capacite", "capacite_m3", "capacite_volume"], "capacite"
    ))


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def ouvrir_session():
    """Ouvre une session SQLAlchemy quel que soit l'emplacement du module."""
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
    raise SystemExit(
        "Impossible d'ouvrir une session.\nTentatives :\n"
        + "\n".join(erreurs)
        + "\n\nDonne-moi la ligne d'import de session utilisee par "
          "scripts/run_solveur.py et je corrige."
    )


# ---------------------------------------------------------------------------
# Rattachement
# ---------------------------------------------------------------------------

def rattacher(lots, matrice) -> dict[int, tuple[int, float, int, float]]:
    """
    Pour chaque lot : (station_aller, distance_aller, station_retour, ecart).

    station_aller  : depot minimisant matrice[depot][destination]  <- la regle
    station_retour : depot minimisant matrice[destination][depot]  <- controle
    ecart          : |d_aller_retenue - d_retour_retenue| en km
    """
    idx_stations = {s: entite_vers_index("station", s)
                    for s in range(1, NB_STATIONS + 1)}
    resultat = {}

    for lot in lots:
        idx_dest = entite_vers_index("destination", lot.id_destination)

        aller = {s: float(matrice[i][idx_dest]) for s, i in idx_stations.items()}
        retour = {s: float(matrice[idx_dest][i]) for s, i in idx_stations.items()}

        s_aller = min(aller, key=aller.get)
        s_retour = min(retour, key=retour.get)

        resultat[lot.id_lot] = (
            s_aller, aller[s_aller],
            s_retour, abs(aller[s_aller] - retour[s_retour]),
        )
    return resultat


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def ligne(largeur: int = 78) -> None:
    print("-" * largeur)


def main() -> None:
    db = ouvrir_session()
    try:
        matrice, noeuds, statut = obtenir_matrice_routiere(db)
        lots = charger_lots(db)
        flotte = charger_flotte(db)
    finally:
        db.close()

    print()
    ligne()
    print("DIAGNOSTIC — rattachement des lots a une station source")
    ligne()
    print(f"Matrice routiere : {matrice.shape[0]}x{matrice.shape[1]}, statut '{statut}'")
    print(f"Lots            : {len(lots)}")
    print(f"Flotte (D23)    : {len(flotte)} vehicules")

    if statut != "valide":
        print()
        print("!! La matrice est perimee. Les rattachements ci-dessous sont")
        print("!! calcules sur un cache invalide — regenere avant de conclure.")

    affectation = rattacher(lots, matrice)

    # --- 1. Repartition par depot ------------------------------------------
    par_depot = defaultdict(list)
    for lot in lots:
        par_depot[affectation[lot.id_lot][0]].append(lot)

    print()
    ligne()
    print("1. REPARTITION DES LOTS PAR DEPOT (sens aller)")
    ligne()
    print(f"{'Depot':<8}{'Lots':>6}{'Volume':>10}{'Dist. moy.':>13}{'Dist. max':>12}")
    for s in range(1, NB_STATIONS + 1):
        groupe = par_depot.get(s, [])
        if not groupe:
            print(f"{s:<8}{0:>6}{'—':>10}{'—':>13}{'—':>12}")
            continue
        distances = [affectation[l.id_lot][1] for l in groupe]
        volume = sum(volume_de(l) for l in groupe)
        print(f"{s:<8}{len(groupe):>6}{volume:>10.2f}"
              f"{sum(distances) / len(distances):>13.1f}{max(distances):>12.1f}")

    # --- 2. Ventilation par type de caisson --------------------------------
    types_lots = sorted({l.caisson_requis for l in lots})

    print()
    ligne()
    print("2. VENTILATION PAR TYPE DE CAISSON REQUIS (volume rattache)")
    ligne()
    entete = f"{'Depot':<8}" + "".join(f"{t:>14}" for t in types_lots)
    print(entete)
    for s in range(1, NB_STATIONS + 1):
        groupe = par_depot.get(s, [])
        cellules = ""
        for t in types_lots:
            sous = [l for l in groupe if l.caisson_requis == t]
            cellules += (f"{len(sous)}×{sum(volume_de(l) for l in sous):.2f}"
                         if sous else "—").rjust(14)
        print(f"{s:<8}{cellules}")

    # --- 3. Flotte par depot ------------------------------------------------
    flotte_depot = defaultdict(list)
    for v in flotte:
        flotte_depot[v.id_station].append(v)

    print()
    ligne()
    print("3. FLOTTE DISPONIBLE PAR DEPOT")
    ligne()
    for s in range(1, NB_STATIONS + 1):
        vehicules = flotte_depot.get(s, [])
        if not vehicules:
            print(f"Depot {s} : AUCUN VEHICULE")
            continue
        detail = ", ".join(
            f"#{v.id_vehicule} {v.type_caisson} ({capacite_de(v):.2f})"
            for v in vehicules
        )
        print(f"Depot {s} : {detail}")

    # --- 4. Lots orphelins --------------------------------------------------
    print()
    ligne()
    print("4. LOTS SANS PORTEUR POSSIBLE APRES RATTACHEMENT")
    ligne()

    orphelins = []
    for lot in lots:
        s = affectation[lot.id_lot][0]
        porteurs = [v for v in flotte_depot.get(s, [])
                    if couvre(v.type_caisson, lot.caisson_requis)]
        if not porteurs:
            orphelins.append((lot, s))

    if not orphelins:
        print("Aucun. Tout lot rattache dispose d'au moins un porteur a son depot.")
    else:
        print(f"{len(orphelins)} lot(s) sur {len(lots)} — ils seront abandonnes")
        print("par les disjonctions D28, pas signales comme erreur.")
        print()
        recap = defaultdict(list)
        for lot, s in orphelins:
            recap[(s, lot.caisson_requis)].append(lot)
        for (s, caisson), groupe in sorted(recap.items()):
            volume = sum(volume_de(l) for l in groupe)
            ids = ", ".join(str(l.id_lot) for l in groupe[:10])
            suite = " ..." if len(groupe) > 10 else ""
            print(f"  Depot {s}, caisson '{caisson}' : {len(groupe)} lot(s), "
                  f"volume {volume:.2f}")
            print(f"    id_lot : {ids}{suite}")

    # --- 5. Capacite par depot et par caisson -------------------------------
    print()
    ligne()
    print("5. CAPACITE CONTRE VOLUME, PAR DEPOT ET PAR TYPE REQUIS")
    ligne()
    print(f"{'Depot':<8}{'Requis':<14}{'Volume':>10}{'Capacite':>11}{'Marge':>10}")

    tendu = False
    for s in range(1, NB_STATIONS + 1):
        groupe = par_depot.get(s, [])
        for t in types_lots:
            volume = sum(volume_de(l) for l in groupe if l.caisson_requis == t)
            if volume == 0:
                continue
            capacite = sum(capacite_de(v) for v in flotte_depot.get(s, [])
                           if couvre(v.type_caisson, t))
            marge = capacite - volume
            drapeau = "  <<<" if marge < 0 else ("  <" if marge < volume * 0.1 else "")
            if marge < volume * 0.1:
                tendu = True
            print(f"{s:<8}{t:<14}{volume:>10.2f}{capacite:>11.2f}"
                  f"{marge:>10.2f}{drapeau}")

    if tendu:
        print()
        print("<<< marge negative : infaisable, lots abandonnes garantis.")
        print("<   marge sous 10 % : le solveur devra remplir presque parfaitement.")
    print()
    print("Note : capacite mutualisee par type. Un lot pris isolement peut")
    print("encore depasser le plus grand vehicule compatible du depot.")

    # --- 6. Effet de l'asymetrie --------------------------------------------
    divergents = [(id_lot, v) for id_lot, v in affectation.items() if v[0] != v[2]]

    print()
    ligne()
    print("6. CONTROLE — EFFET DE L'ASYMETRIE DE LA MATRICE")
    ligne()
    print(f"{len(divergents)} lot(s) sur {len(lots)} changeraient de depot si le")
    print("rattachement etait calcule sur le trajet retour au lieu de l'aller.")
    if divergents:
        pire = max(divergents, key=lambda x: x[1][3])
        print(f"Ecart maximal : {pire[1][3]:.1f} km (lot {pire[0]}, "
              f"depot {pire[1][0]} a l'aller contre {pire[1][2]} au retour).")
        print("Le sens aller est retenu : c'est celui du chargement au depot.")
    print()


if __name__ == "__main__":
    main()
