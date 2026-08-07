# app/services/clustering.py
"""Zonage geographique des destinations par clustering (ML).

Principe (registre D-serie "zonage") :
  - On regroupe les 100 destinations en k zones geographiques par k-means.
  - La zone est une VUE analytique, PAS un fait de la destination : rien
    n'est stocke en base (pas de colonne 'zone' sur Destination). Le mapping
    est recalcule a la lecture, comme les resumes de run. Meme entree + meme
    graine => meme sortie, donc reproductible sans persistance.

Choix methodologiques verrouilles :
  - Metrique : coordonnees PROJETEES en km (equirectangulaire), pas lat/lon
    brut. A ~35.7 N, 1 deg de longitude ne vaut que cos(lat)~0.81 fois 1 deg
    de latitude ; sans correction k-means ecrase l'axe est-ouest (~19 %).
    Projection : x = R*cos(lat_moy)*lon, y = R*lat  (R = 111.32 km/deg).
  - Algorithme : k-means (random_state=42, n_init=10). Contre-epreuve Ward
    faite hors-ligne : accord <0.01 de silhouette => decoupage robuste.
  - k = 7 (pic silhouette 0.532 ; zones lisibles : Grand Tunis, Nord-Ouest,
    Sahel, Centre, Sfax, Djerid, Sud-Est). k=5 (aligne depots) est le creux
    => la geographie ne suit PAS la partition D32, d'ou couche SEPAREE.
  - Numerotation RENUMEROTEE nord->sud (centroide decroissant en latitude) :
    id_zone stable et lisible, independant des labels internes de k-means.

Les depots (table Station) ne sont PAS clusterises : seule la table
Destination alimente le zonage.
"""
from app.models.destination import Destination
from sqlalchemy.orm import Session
from sklearn.cluster import KMeans
import numpy as np
import os
# Windows + Python recent : loky ne trouve pas 'wmic' pour compter les coeurs
# physiques et emet un UserWarning bruyant a chaque fit. On fixe la variable
# AVANT l'import sklearn (valeur = coeurs logiques, ce que loky utilise de
# toute facon en repli). Sans effet sur le resultat, juste sur le bruit.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))


# Approximation equirectangulaire : km par degre.
KM_PAR_DEGRE = 111.32
# Nombre de zones verrouille (D-serie zonage). Parametrable ; defaut = 7.
K_ZONES = 7
# Graine partagee du projet (coherence avec seed_lots, RNG 42).
GRAINE = 42


def _projeter(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Projette lat/lon (deg) en plan (x, y) en km, localement isotrope.

    Repere equirectangulaire centre sur la latitude moyenne du nuage : la
    distance euclidienne dans (x, y) ~ distance au sol. Sans ca, k-means
    surponderait l'ecart est-ouest (facteur cos(lat)).
    """
    lat_moy = float(lat.mean())
    x = KM_PAR_DEGRE * np.cos(np.radians(lat_moy)) * lon
    y = KM_PAR_DEGRE * lat
    return np.column_stack([x, y])


def clusteriser(points: list[dict], k: int = K_ZONES) -> dict:
    """Coeur ML pur : une zone par destination, sans base ni etat.

    'points' : [{"id_destination": int, "lat": float, "lon": float}, ...].
    Deterministe et testable isolement.

    Etapes : tri par id_destination (ordre d'entree fixe => reproductible),
    projection km, k-means, puis renumerotation nord->sud des zones.

    Retour :
      {
        "k": k,
        "mapping": {id_destination: id_zone},   # id_zone dans 1..k
        "zones": [
          {"id_zone": 1, "n": 37,
           "centre": {"lat": .., "lon": ..},     # centroide geographique reel
           "destinations": [id_destination, ...]},
          ...
        ],
      }
    """
    pts = sorted(points, key=lambda p: p["id_destination"])
    if len(pts) < k:
        raise ValueError(
            f"{len(pts)} destination(s) pour k={k} : pas assez de points."
        )

    ids = np.array([p["id_destination"] for p in pts])
    lat = np.array([float(p["lat"]) for p in pts], dtype=float)
    lon = np.array([float(p["lon"]) for p in pts], dtype=float)

    X = _projeter(lat, lon)
    labels = KMeans(n_clusters=k, random_state=GRAINE, n_init=10).fit_predict(X)

    # Centroide GEOGRAPHIQUE (lat/lon reels) de chaque cluster brut.
    centres_lat = np.array([lat[labels == c].mean() for c in range(k)])
    centres_lon = np.array([lon[labels == c].mean() for c in range(k)])

    # Renumerotation nord->sud : cluster le plus au nord => Zone 1.
    ordre = np.argsort(-centres_lat)                  # labels bruts, nord d'abord
    label_vers_zone = {int(brut): i + 1 for i, brut in enumerate(ordre)}

    mapping = {
        int(ids[j]): label_vers_zone[int(labels[j])]
        for j in range(len(ids))
    }

    zones = []
    for i, brut in enumerate(ordre):
        membres = [int(ids[j]) for j in range(len(ids)) if labels[j] == brut]
        zones.append({
            "id_zone": i + 1,
            "n": len(membres),
            "centre": {
                "lat": round(float(centres_lat[brut]), 6),
                "lon": round(float(centres_lon[brut]), 6),
            },
            "destinations": sorted(membres),
        })

    return {"k": k, "mapping": mapping, "zones": zones}


def calculer_zones(db: Session, k: int = K_ZONES) -> dict:
    """Charge les destinations de la base et delegue a clusteriser().

    Lecture seule : aucune ecriture, aucune colonne 'zone' persistee. Meme
    contrat de sortie que clusteriser(). Ordre de chargement fixe par
    id_destination => reproductible.
    """
    dest = (
        db.query(Destination)
        .order_by(Destination.id_destination)
        .all()
    )
    points = [
        {
            "id_destination": d.id_destination,
            "lat": float(d.latitude),
            "lon": float(d.longitude),
        }
        for d in dest
    ]
    return clusteriser(points, k=k)
