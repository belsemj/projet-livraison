# app/services/kpis.py
from typing import Optional
from statistics import pstdev
from sqlalchemy.orm import Session
from app.crud import run as crud_run
from app.crud.carte import assembler_carte
from app.models.tournee import Tournee
from app.models.vehicule import Vehicule


def _stats(valeurs: list[float]) -> dict:
    """Dispersion d'une grandeur entre les tournees d'un run.

    ecart_type = ecart-type de POPULATION (pstdev) : on decrit la dispersion
    sur TOUTES les tournees du run (l'ensemble complet, pas un echantillon).
    pstdev est aussi defini pour n=1 (renvoie 0.0), la ou stdev leverait.
    Liste vide (run sans tournee, tout abandonne) -> zeros.
    """
    if not valeurs:
        return {"min": 0.0, "max": 0.0, "moyenne": 0.0, "ecart_type": 0.0}
    return {
        "min": round(min(valeurs), 2),
        "max": round(max(valeurs), 2),
        "moyenne": round(sum(valeurs) / len(valeurs), 2),
        "ecart_type": round(pstdev(valeurs), 2),
    }


def calculer_kpis(db: Session, id_run: int) -> Optional[dict]:
    """KPIs d'un run, calcules a la LECTURE (aucun stockage).

    Principe : on ne recompte RIEN qui existe deja ailleurs, pour ne pas
    recreer la divergence J2 (carte vs resume).
      - distance + servis/non servis : repris TELS QUELS du resume du run
        (crud_run.lire_run) -> identiques a l'ecran detail.
      - destinations servies / abandonnees : LUES depuis assembler_carte
        (statut D33-carto : 'servie' / 'abandonnee' / 'hors_vague'), jamais
        recalculees ici.
      - seul fait AJOUTE par les KPIs : la capacite vehicule -> remplissage
        (charge / capacite) et equilibrage (dispersion volume + distance).

    Deux comptes de lots servis, volontairement distincts et honnetes :
      - nb_lots_servis          : nombre d'AFFECTATIONS (= ecran detail ; un
                                  lot fractionne compte plusieurs fois),
      - nb_lots_distincts_servis : nombre de lots distincts reellement livres.

    Retourne None si le run n'existe pas (propage le None de lire_run -> 404).

    Cout : lire_run + assembler_carte + une requete capacite = 3 passes sur le
    meme run. Sans incidence a l'echelle du projet ; fusionnable / cachable
    plus tard (facon matrices / zonage) si l'historique grossit.
    """
    base = crud_run.lire_run(db, id_run)
    if base is None:
        return None

    # Capacite par tournee : le SEUL fait absent du resume du run.
    caps = dict(
        db.query(Tournee.id_tournee, Vehicule.capacite)
        .join(Vehicule, Tournee.id_vehicule == Vehicule.id_vehicule)
        .filter(Tournee.id_run == id_run)
        .all()
    )

    tournees_kpi: list[dict] = []
    charges: list[float] = []
    distances: list[float] = []
    remplissages: list[float] = []
    lots_distincts: set[int] = set()

    for t in base["tournees"]:
        charge = round(sum(a["quantite"] for a in t["affectations"]), 2)
        capacite = float(caps.get(t["id_tournee"]) or 0)
        distance = round(t["distance_totale"] or 0.0, 2)
        # Garde-fou : capacite > 0 par contrainte schema (chk_veh_cap),
        # on protege quand meme la division.
        remplissage = round(100 * charge / capacite, 1) if capacite > 0 else 0.0

        for a in t["affectations"]:
            lots_distincts.add(a["id_lot"])

        charges.append(charge)
        distances.append(distance)
        remplissages.append(remplissage)
        tournees_kpi.append(
            {
                "id_tournee": t["id_tournee"],
                "id_vehicule": t["id_vehicule"],
                "charge_volume": charge,
                "capacite": round(capacite, 2),
                "remplissage_pct": remplissage,
                "distance_km": distance,
            }
        )

    remplissage_moyen = (
        round(sum(remplissages) / len(remplissages), 1) if remplissages else 0.0
    )

    # Destinations : LU depuis assembler_carte (statut D33), jamais recalcule.
    # assembler_carte renvoie None seulement si le run n'existe pas, cas deja
    # ecarte par lire_run ci-dessus ; on garde une garde defensive.
    carte = assembler_carte(db, id_run)
    dests = carte["destinations"] if carte else []
    nb_dest_servies = sum(1 for d in dests if d["statut"] == "servie")
    nb_dest_abandonnees = sum(1 for d in dests if d["statut"] == "abandonnee")

    return {
        "id_run": base["id_run"],
        "nb_tournees": base["nb_tournees"],
        # Distance (repris du resume -> identique au detail)
        "distance_totale_km": base["distance_totale_km"],
        # Taux d'utilisation
        "remplissage_moyen_pct": remplissage_moyen,
        # Equilibrage (sur volume ET distance)
        "equilibrage_volume": _stats(charges),
        "equilibrage_distance": _stats(distances),
        # Servis / non servis
        "nb_lots_servis": base["nb_lots_servis"],
        "nb_lots_distincts_servis": len(lots_distincts),
        "nb_lots_non_servis": base["nb_lots_non_servis"],
        "nb_destinations_servies": nb_dest_servies,
        "nb_destinations_abandonnees": nb_dest_abandonnees,
        # Detail par tournee
        "tournees": tournees_kpi,
    }
