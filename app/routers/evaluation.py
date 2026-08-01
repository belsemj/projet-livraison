"""
Evaluation d'une affectation manuelle (Phase 2, S7 J4).

POST /evaluations : recoit une affectation figee par l'humain (vague + couples
chauffeur/vehicule + lots imposes), controle sa coherence (violations non
bloquantes) et reordonne chaque tournee par TSP. LECTURE SEULE : rien n'est
persiste, contrairement a POST /optimisations. Aucune logique metier ici --
on adapte la requete au service evaluateur et on met en forme sa reponse.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.evaluation import (
    EvaluationRequete,
    EvaluationResultat,
    TourneeEvaluee,
)
from app.services import evaluateur
from app.services.matrice_etendue import ECHELLE

router = APIRouter(prefix="/evaluations", tags=["evaluation"])


@router.post("", response_model=EvaluationResultat,
             summary="Evaluer une affectation manuelle")
def evaluer_affectation(
    requete: EvaluationRequete,
    db: Session = Depends(get_db),
):
    """
    Evalue une affectation manuelle : controles non bloquants + reordonnancement
    TSP par tournee. Ne persiste rien.

    - 200 : evaluation renvoyee (ordre optimise, perf, violations, agregat).
    - 422 : donnees d'entree invalides (vehicule ou lot introuvable).
    - 500 : matrice routiere absente (relancer scripts/build_distances.py).
    """
    # --- adaptation requete -> entree service ----------------------------
    affectations = [
        evaluateur.TourneeImposee(
            id_chauffeur=a.id_chauffeur,
            id_vehicule=a.id_vehicule,
            ids_lots=a.ids_lots,
        )
        for a in requete.affectations
    ]

    try:
        ev = evaluateur.evaluer(db, requete.id_vague, affectations)
    except ValueError as e:
        # vehicule ou lot introuvable : donnee d'entree invalide.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except FileNotFoundError as e:
        # matrice routiere non generee : incident d'exploitation, pas d'entree.
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Matrice routiere indisponible : {e}",
        )

    # --- mise en forme : metres -> km, echelle -> m3 ---------------------
    tournees = [
        TourneeEvaluee(
            id_chauffeur=t.id_chauffeur,
            id_vehicule=t.id_vehicule,
            id_station_depart=t.id_station_depart,
            ordre_lots=t.ordre_lots,
            distance_km=round(t.distance_m / 1000, 2),
            charge_m3=round(t.charge_echelle / ECHELLE, 2),
            capacite_m3=round(t.capacite_echelle / ECHELLE, 2),
            taux_charge=round(t.taux_charge, 1),
            violations=t.violations,      # dataclasses -> from_attributes
        )
        for t in ev.tournees
    ]

    return EvaluationResultat(
        distance_totale_km=round(ev.distance_totale_m / 1000, 2),
        nb_tournees=len(ev.tournees),
        nb_violations=ev.nb_violations,
        lots_non_affectes=ev.lots_non_affectes,
        tournees=tournees,
    )
