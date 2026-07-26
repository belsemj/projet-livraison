from collections import defaultdict
from typing import Optional
from sqlalchemy.orm import Session, selectinload
from app.models.tournee import Tournee


def lire_run(db: Session, id_run: int) -> Optional[dict]:
    """Reconstruit un run a partir de ses tournees.

    Il n'existe pas de table 'run' : id_run vit sur 'tournee' uniquement.
    Le resume (nb tournees, lots servis, distance) est recalcule a la lecture.
    Retourne None si aucune tournee ne porte cet id_run (-> 404 cote router).
    """
    tournees = (
        db.query(Tournee)
        .filter(Tournee.id_run == id_run)
        .options(selectinload(Tournee.affectations))
        .order_by(Tournee.id_tournee)
        .all()
    )

    if not tournees:
        return None

    # Ordonner les arrets de chaque tournee par ordre de visite
    for t in tournees:
        t.affectations.sort(key=lambda a: a.ordre_visite)

    nb_lots_servis = sum(len(t.affectations) for t in tournees)
    distance_totale_km = round(
        sum(float(t.distance_totale or 0) for t in tournees), 2
    )

    return {
        "id_run": id_run,
        "nb_tournees": len(tournees),
        "nb_lots_servis": nb_lots_servis,
        "distance_totale_km": distance_totale_km,
        "tournees": tournees,
    }


def lister_runs(db: Session) -> list[dict]:
    """Liste tous les runs existants avec un resume, plus recent d'abord.

    Il n'existe pas de table 'run' : on regroupe les tournees par id_run et on
    recalcule le resume a la lecture, avec exactement la meme logique que
    lire_run (lots servis = nb d'affectations, distance = somme des tournees)
    pour garantir la coherence liste <-> detail.

    'date_calcul' du run = MAX des date_calcul de ses tournees (elles sont
    creees d'un bloc au moment du solve, donc quasi identiques).

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
                "distance_totale_km": distance_totale_km,
                "date_calcul": date_calcul,
            }
        )

    # Plus recent d'abord (id_run decroissant)
    resumes.sort(key=lambda r: r["id_run"], reverse=True)
    return resumes
