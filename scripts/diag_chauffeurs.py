"""
Diagnostic LECTURE SEULE des chauffeurs.

Repere les lignes qui feraient echouer la serialisation Pydantic de
ChauffeurRead (statut hors Literal["actif","conge","maladie"], id_depot NULL),
cause probable du 500 sur GET /chauffeurs/.

Lancer depuis la racine du projet :
    python -m scripts.diag_chauffeurs
"""

from app.database import SessionLocal
from app.models.chauffeur import Chauffeur

STATUTS_OK = {"actif", "conge", "maladie"}


def main() -> None:
    db = SessionLocal()
    try:
        lignes = db.query(Chauffeur).all()
        print(f"Total chauffeurs : {len(lignes)}\n")

        statuts = sorted({c.statut for c in lignes})
        print(f"Statuts presents en base : {statuts}")
        print(f"Statuts admis par ChauffeurRead : {sorted(STATUTS_OK)}\n")

        suspects = [
            c for c in lignes
            if c.statut not in STATUTS_OK or c.id_depot is None
        ]

        if not suspects:
            print("Aucune ligne suspecte cote statut/id_depot.")
            print("=> La 500 vient d'ailleurs : regarder le traceback Uvicorn.")
        else:
            print(f"{len(suspects)} ligne(s) suspecte(s) :")
            for c in suspects:
                raison = []
                if c.statut not in STATUTS_OK:
                    raison.append(f"statut='{c.statut}'")
                if c.id_depot is None:
                    raison.append("id_depot=NULL")
                print(f"  - id={c.id_chauffeur} nom={c.nom!r} "
                      f"({', '.join(raison)})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
