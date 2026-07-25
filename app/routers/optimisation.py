"""
Lancement du solveur et persistance du resultat (S6 J1).

POST /optimisations : construit le contexte a partir de l'etat courant de la
base, execute le solveur MDVRP en synchrone, persiste les tournees non vides
et leurs affectations sous un nouvel id_run, et renvoie un resume. Le detail
imbrique (tournees + affectations) est du ressort de GET /runs/{id_run} (J2).

Seule ecriture cote optimisation. Aucune logique metier n'est ajoutee ici :
on orchestre lecture des donnees, appel au solveur, ecriture du resultat.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import optimisation as crud
from app.schemas.optimisation import OptimisationRequete, OptimisationResultat
from app.services import solveur
from app.services.matrice_etendue import construire_contexte, controler

router = APIRouter(prefix="/optimisations", tags=["optimisation"])


@router.post("", response_model=OptimisationResultat,
             status_code=status.HTTP_201_CREATED,
             summary="Lancer une optimisation")
def lancer_optimisation(
    requete: Optional[OptimisationRequete] = None,
    db: Session = Depends(get_db),
):
    """
    Execute le solveur sur l'etat courant de la base et persiste le resultat.

    - 201 : run cree ; resume renvoye (id_run, distances, lots servis).
    - 422 : donnees insuffisantes (aucun lot, ou flotte mobilisable vide).
    - 409 : anomalies bloquantes dans les donnees (a corriger avant d'optimiser).
    - 500 : echec du solveur, ou echec de la persistance.
    """
    # 1. Contexte -- une seule lecture de la base.
    try:
        ctx = construire_contexte(db)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # 2. Controle de coherence. Les lignes '[info]' ne sont pas bloquantes :
    #    elles annoncent des lots que le solveur abandonnera proprement par
    #    disjonction (depot sans porteur du bon caisson).
    anomalies = controler(ctx)
    bloquantes = [m for m in anomalies if not m.startswith("[info]")]
    avertissements = [m for m in anomalies if m.startswith("[info]")]
    if bloquantes:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": "Donnees a corriger avant optimisation.",
                    "anomalies": bloquantes},
        )

    # 3. Resolution synchrone. limite_secondes optionnel ; defaut 60 s (S5).
    limite = (requete.limite_secondes if requete else None) or solveur.LIMITE_SECONDES
    res = solveur.resoudre(ctx, limite_secondes=limite)
    if res.statut != "resolu":
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Le solveur n'a pas produit de solution.",
        )

    # 4. Persistance tout-ou-rien.
    try:
        id_run = crud.prochain_id_run(db)
        crud.persister(db, res, ctx, id_run)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Echec de la persistance du resultat.",
        )

    servis = len(ctx.lots) - len(res.lots_non_servis)
    return OptimisationResultat(
        id_run=id_run,
        statut=res.statut,
        distance_totale_km=round(res.distance_totale_m / 1000, 2),
        nb_tournees=res.nb_vehicules_utilises,
        nb_lots_servis=servis,
        nb_lots_non_servis=len(res.lots_non_servis),
        lots_non_servis=res.lots_non_servis,
        avertissements=avertissements,
    )
