"""
Persistance d'un run d'optimisation (S6 J1).

Traduit un Resultat de solveur en lignes `tournee` et `affectation`, sous un
id_run donne. Deux ecarts entre le resultat solveur et le schema y sont
resorbes ici, sans toucher au solveur (principe schema vs solveur) :

  - id_chauffeur : NOT NULL sur `tournee`, absent du resultat (qui ne porte
    que id_vehicule). Resolu par une lecture {id_vehicule -> id_chauffeur}.
  - quantite : le modele place UN noeud par lot (pas de fractionnement
    effectif), donc chaque affectation porte le volume entier du lot en m3.

Seules les tournees NON VIDES sont persistees : un vehicule inutilise renvoie
id_station_retour=None (or la colonne est NOT NULL) et n'a pas de sens metier.

Ne commit pas : la transaction est pilotee par le routeur (tout-ou-rien).
"""

from sqlalchemy import func

from app.models.tournee import Tournee
from app.models.affectation import Affectation
from app.models.vehicule import Vehicule
from app.models.lot import Lot


def prochain_id_run(db) -> int:
    """MAX(id_run) + 1 ; 1 si aucune tournee n'existe encore."""
    maxi = db.query(func.max(Tournee.id_run)).scalar()
    return 1 if maxi is None else int(maxi) + 1


def persister(db, res, ctx, id_run: int) -> None:
    """Ecrit les tournees non vides et leurs affectations pour `id_run`."""
    tournees_pleines = [t for t in res.tournees if t.lots]

    # id_vehicule -> id_chauffeur (une lecture pour toute la flotte utilisee).
    # id_chauffeur est garanti non nul : charger_flotte l'exige (D23).
    ids_veh = [t.id_vehicule for t in tournees_pleines]
    chauffeur_par_vehicule = dict(
        db.query(Vehicule.id_vehicule, Vehicule.id_chauffeur)
        .filter(Vehicule.id_vehicule.in_(ids_veh))
        .all()
    )

    # volume reel (m3) de chaque lot servi, pour affectation.quantite.
    ids_lot = [id_lot for t in tournees_pleines for id_lot in t.lots]
    volume_par_lot = dict(
        db.query(Lot.id_lot, Lot.volume).filter(Lot.id_lot.in_(ids_lot)).all()
    ) if ids_lot else {}

    for t in tournees_pleines:
        tournee = Tournee(
            id_run=id_run,
            distance_totale=round(t.distance_m / 1000, 2),   # metres -> km
            statut="planifiee",
            id_station_depart=t.id_station_depart,
            id_station_retour=t.id_station_retour,           # == depart (D34)
            id_chauffeur=chauffeur_par_vehicule[t.id_vehicule],
            id_vehicule=t.id_vehicule,
        )
        db.add(tournee)
        db.flush()   # affecte tournee.id_tournee avant les affectations

        for ordre, id_lot in enumerate(t.lots, start=1):
            db.add(Affectation(
                ordre_visite=ordre,
                quantite=round(float(volume_par_lot[id_lot]), 2),
                id_tournee=tournee.id_tournee,
                id_lot=id_lot,
            ))
