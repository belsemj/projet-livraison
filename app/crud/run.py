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
