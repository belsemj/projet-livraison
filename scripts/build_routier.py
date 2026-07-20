"""
S4 J3 - Etape 4 : generation de la matrice routiere complete.

Usage :
    python scripts/build_routier.py
    python scripts/build_routier.py --forcer
"""

import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.database import SessionLocal  # noqa: E402
from app.services import routage  # noqa: E402
from app.services.distances import DOSSIER_DONNEES  # noqa: E402


def main():
    forcer = "--forcer" in sys.argv
    session = SessionLocal()

    try:
        matrice, noeuds, motif = routage.obtenir_matrice(session, forcer=forcer)
        print(f"\nMatrice routiere : {matrice.shape}, motif = {motif}")

        chemin_geo = DOSSIER_DONNEES / "matrice_geodesique.npy"
        geodesique = np.load(chemin_geo) if chemin_geo.exists() else None

        anomalies = routage.controler(matrice, noeuds, geodesique)
        if anomalies:
            print(f"\n{len(anomalies)} signalement(s) :")
            for message in anomalies[:15]:
                print(f"  {message}")
        else:
            print("\nAucun signalement.")

        if geodesique is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.where(geodesique > 0, matrice / geodesique, np.nan)
            valeurs = ratio[np.isfinite(ratio)]
            print("\nRatio routier / geodesique sur la matrice complete")
            print(f"  paires    : {valeurs.size}")
            print(f"  moyenne   : {valeurs.mean():.4f}")
            print(f"  mediane   : {np.median(valeurs):.4f}")
            print(f"  ecart-type: {valeurs.std():.4f}")
            print(f"  min / max : {valeurs.min():.4f} / {valeurs.max():.4f}")

            ecarts = np.abs(matrice - matrice.T)
            ecarts = ecarts[np.isfinite(ecarts)]
            print("\nAsymetrie aller / retour (km)")
            print(f"  moyenne : {ecarts.mean():.3f}   maximum : {ecarts.max():.3f}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
