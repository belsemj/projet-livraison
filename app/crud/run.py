from collections import defaultdict
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from app.models.tournee import Tournee
from app.models.lot import Lot
from app.models.destination import Destination
from app.models.lot_non_servi import LotNonServi as LotNonServiRow


def lire_run(db: Session, id_run: int) -> Optional[dict]:
    """Reconstruit un run a partir de ses tournees.

    Il n'existe pas de table 'run' : id_run vit sur 'tournee' uniquement.
    Le resume (nb tournees, lots servis, distance) est recalcule a la lecture.
    Retourne None si aucune tournee ne porte cet id_run (-> 404 cote router).

    S7 J3 : les lots non servis du run sont desormais PERSISTES (table
    lot_non_servi) ; on les relit avec leur destination pour le popup carte et
    le detail. C'est le meme fait que celui affiche par le resume POST, plus une
    inference concurrente.
    """
    tournees = (
        db.query(Tournee)
        .filter(Tournee.id_run == id_run)
        .options(selectinload(Tournee.affectations))
        .order_by(Tournee.id_tournee)
        .all()
    )

    # Un run peut n'avoir AUCUNE tournee et pourtant exister via des lots non
    # servis (cas extreme : tout abandonne). On considere le run inexistant
    # seulement si NI tournee NI lot non servi ne porte cet id_run.
    lns_rows = (
        db.query(
            LotNonServiRow.id_lot,
            LotNonServiRow.raison,
            Destination.id_destination,
            Destination.nom,
        )
        .join(Lot, LotNonServiRow.id_lot == Lot.id_lot)
        .join(Destination, Lot.id_destination == Destination.id_destination)
        .filter(LotNonServiRow.id_run == id_run)
        .order_by(LotNonServiRow.id_lot)
        .all()
    )

    if not tournees and not lns_rows:
        return None

    # Ordonner les arrets de chaque tournee par ordre de visite
    for t in tournees:
        t.affectations.sort(key=lambda a: a.ordre_visite)

    # Carte id_lot -> destination (id + nom). Chaque lot appartient a une
    # destination ; on remonte le nom pour un affichage lisible cote front,
    # sans se contenter de l'id brut (revision de D32).
    ids_lots = {a.id_lot for t in tournees for a in t.affectations}
    dest_par_lot: dict[int, dict] = {}
    if ids_lots:
        lignes = (
            db.query(Lot.id_lot, Destination.id_destination, Destination.nom)
            .join(Destination, Lot.id_destination == Destination.id_destination)
            .filter(Lot.id_lot.in_(ids_lots))
            .all()
        )
        dest_par_lot = {
            id_lot: {"id_destination": id_dest, "nom_destination": nom}
            for id_lot, id_dest, nom in lignes
        }

    nb_lots_servis = sum(len(t.affectations) for t in tournees)
    distance_totale_km = round(
        sum(float(t.distance_totale or 0) for t in tournees), 2
    )

    # Construction explicite de la reponse (dicts) pour injecter la destination
    # au niveau arret, champs absents du modele Affectation.
    tournees_out = []
    for t in tournees:
        arrets_out = []
        for a in t.affectations:
            info = dest_par_lot.get(a.id_lot) or {}
            arrets_out.append(
                {
                    "ordre_visite": a.ordre_visite,
                    "id_lot": a.id_lot,
                    "id_destination": info.get("id_destination"),
                    "nom_destination": info.get("nom_destination"),
                    "quantite": float(a.quantite),
                }
            )
        tournees_out.append(
            {
                "id_tournee": t.id_tournee,
                "id_vehicule": t.id_vehicule,
                "id_chauffeur": t.id_chauffeur,
                "id_station_depart": t.id_station_depart,
                "id_station_retour": t.id_station_retour,
                "distance_totale": (
                    float(t.distance_totale)
                    if t.distance_totale is not None
                    else None
                ),
                "statut": t.statut,
                "affectations": arrets_out,
            }
        )

    # Lots non servis persistes (id_lot, raison, destination pour le popup).
    lots_non_servis_out = [
        {
            "id_lot": id_lot,
            "raison": raison,
            "id_destination": id_dest,
            "nom_destination": nom,
        }
        for id_lot, raison, id_dest, nom in lns_rows
    ]

    return {
        "id_run": id_run,
        "nb_tournees": len(tournees),
        "nb_lots_servis": nb_lots_servis,
        "nb_lots_non_servis": len(lots_non_servis_out),
        "distance_totale_km": distance_totale_km,
        "tournees": tournees_out,
        "lots_non_servis": lots_non_servis_out,
    }


def lister_runs(db: Session) -> list[dict]:
    """Liste tous les runs existants avec un resume, plus recent d'abord.

    Il n'existe pas de table 'run' : on regroupe les tournees par id_run et on
    recalcule le resume a la lecture, avec exactement la meme logique que
    lire_run (lots servis = nb d'affectations, distance = somme des tournees)
    pour garantir la coherence liste <-> detail.

    'date_calcul' du run = MAX des date_calcul de ses tournees (elles sont
    creees d'un bloc au moment du solve, donc quasi identiques).

    S7 J3 : on joint le compte des lots non servis persistes par run
    (nb_lots_non_servis), pour que le selecteur de run l'affiche.

    Note : on charge les tournees + affectations en memoire. Sur le volume du
    projet c'est sans cout ; si l'historique grossit beaucoup, remplacer par
    des agregations SQL (GROUP BY id_run) sur tournee et affectation.
    """
    tournees = (
        db.query(Tournee)
        .options(selectinload(Tournee.affectations))
        .all()
    )

    if not tournees:
        return []

    # Compte des lots non servis par run (une agregation, pas un chargement).
    nb_non_servis_par_run = dict(
        db.query(LotNonServiRow.id_run, func.count(LotNonServiRow.id_lot_non_servi))
        .group_by(LotNonServiRow.id_run)
        .all()
    )

    # Regrouper les tournees par run
    par_run: dict[int, list[Tournee]] = defaultdict(list)
    for t in tournees:
        par_run[t.id_run].append(t)

    resumes = []
    for id_run, ts in par_run.items():
        nb_lots_servis = sum(len(t.affectations) for t in ts)
        distance_totale_km = round(
            sum(float(t.distance_totale or 0) for t in ts), 2
        )
        date_calcul = max(t.date_calcul for t in ts)
        resumes.append(
            {
                "id_run": id_run,
                "nb_tournees": len(ts),
                "nb_lots_servis": nb_lots_servis,
                "nb_lots_non_servis": int(nb_non_servis_par_run.get(id_run, 0)),
                "distance_totale_km": distance_totale_km,
                "date_calcul": date_calcul,
            }
        )

    # Plus recent d'abord (id_run decroissant)
    resumes.sort(key=lambda r: r["id_run"], reverse=True)
    return resumes
