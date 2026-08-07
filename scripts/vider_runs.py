"""
Vide les runs d'optimisation (tournees + affectations + lots non servis).

id_run n'est pas une sequence : il est calcule par MAX(id_run)+1 a chaque
POST. Vider ces tables suffit donc a faire repartir la numerotation a 1 au
prochain lancement -- aucun compteur a reinitialiser.

la table lot_non_servi (lots abandonnes par run + raison) fait
desormais partie d'un run. On la purge ici aussi ; sinon des lignes
orphelines subsistent et bloquent la FK lot_non_servi.id_lot -> lot.

Les tables d'ENTREE (station, destination, lot, vehicule, chauffeur) ne
sont PAS touchees : on n'efface que les resultats produits par le solveur.

Usage (depuis la racine) :
    python -m scripts.vider_runs
"""

from app.database import SessionLocal
from app.models.tournee import Tournee
from app.models.affectation import Affectation
from app.models.lot_non_servi import LotNonServi


def main() -> None:
    db = SessionLocal()
    try:
        # Ordre : affectation (FK -> tournee) avant tournee. lot_non_servi n'a
        # pas de FK vers tournee (id_run est un simple entier) : ordre libre.
        nb_aff = db.query(Affectation).delete()
        nb_lns = db.query(LotNonServi).delete()
        nb_tour = db.query(Tournee).delete()
        db.commit()
        print(
            f"supprime : {nb_aff} affectations, {nb_lns} lots non servis, "
            f"{nb_tour} tournees"
        )
        print("le prochain POST /optimisations repartira a id_run = 1")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
