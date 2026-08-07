"""
Controle de coherence de bout en bout (lecture seule).

Parcourt la chaine stations.csv -> livraison.db -> noeuds.csv -> matrices
et rend un verdict par maillon. N'ecrit rien, ne corrige rien : il signale.

Lancement depuis la racine du projet :
    python -m scripts.controle_coherence
"""
import csv
import sys
from pathlib import Path

import numpy as np

from app.database import SessionLocal
from app.models.station import Station
from app.models.destination import Destination
from app.services import distances as svc

RACINE = Path(__file__).resolve().parents[1]
DATA = RACINE / "data"
TOLERANCE_GPS = 1e-6      # ~0.1 m : egalite stricte a l'arrondi pres
anomalies = []


def verdict(libelle, ok, detail=""):
    marque = "OK  " if ok else "ECHEC"
    print(f"  [{marque}] {libelle}" + (f" — {detail}" if detail else ""))
    if not ok:
        anomalies.append(libelle)


def champ(n, *noms):
    """Accede a un attribut de Noeud, qu'il soit objet ou dictionnaire."""
    for nom in noms:
        if hasattr(n, nom):
            return getattr(n, nom)
        if isinstance(n, dict) and nom in n:
            return n[nom]
    return None


# ---------------------------------------------------------------- maillon 1
def maillon_stations_csv(db):
    print("\n1. stations.csv -> base de donnees")
    chemin = DATA / "stations.csv"
    if not chemin.exists():
        verdict("fichier stations.csv present", False, str(chemin))
        return

    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f))
    verdict("lecture du fichier de reference", True, f"{len(lignes)} lignes")

    colonnes = set(lignes[0].keys()) if lignes else set()
    col_lat = next((c for c in colonnes if "lat" in c.lower()), None)
    col_lon = next((c for c in colonnes if "lon" in c.lower() or "lng" in c.lower()), None)
    col_nom = next((c for c in colonnes if c.lower() in ("nom", "nom_station", "name")), None)
    if not (col_lat and col_lon and col_nom):
        verdict("colonnes lat/lon/nom identifiees", False, f"colonnes vues : {sorted(colonnes)}")
        return

    ecarts = 0
    for ligne in lignes:
        nom = ligne[col_nom].strip()
        st = db.query(Station).filter(Station.nom == nom).first()
        if st is None:
            continue  # les destinations du csv ne sont pas des stations
        dlat = abs(float(st.latitude) - float(ligne[col_lat]))
        dlon = abs(float(st.longitude) - float(ligne[col_lon]))
        if dlat > TOLERANCE_GPS or dlon > TOLERANCE_GPS:
            ecarts += 1
            print(f"        divergence : {nom} "
                  f"csv=({ligne[col_lat]}, {ligne[col_lon]}) "
                  f"db=({st.latitude}, {st.longitude})")
    verdict("coordonnees des depots alignees sur la reference", ecarts == 0,
            f"{ecarts} divergence(s)")


# ---------------------------------------------------------------- maillon 2
def maillon_seed(db):
    print("\n2. base de donnees <-> seed.sql")
    chemin = DATA / "seed.sql"
    if not chemin.exists():
        verdict("fichier seed.sql present", False)
        return
    texte = chemin.read_text(encoding="utf-8", errors="replace")

    n_st = db.query(Station).count()
    n_de = db.query(Destination).count()
    verdict("volumetrie en base", n_st == 5 and n_de == 100,
            f"{n_st} stations, {n_de} destinations")

    # traces des corrections : ce qui a ete retire ne doit plus apparaitre
    for terme in ("Kerkennah",):
        verdict(f"aucune trace residuelle de « {terme} » dans seed.sql",
                terme.lower() not in texte.lower())
    for terme in ("Jebeniana",):
        verdict(f"correction « {terme} » presente dans seed.sql",
                terme.lower() in texte.lower())

    en_base = {d.nom for d in db.query(Destination).all()}
    verdict("aucune trace residuelle de « Kerkennah » en base",
            not any("kerkennah" in n.lower() for n in en_base))


# ---------------------------------------------------------------- maillon 3
def maillon_noeuds(db):
    print("\n3. base de donnees -> noeuds.csv")
    noeuds = svc.charger_noeuds(db)
    verdict("nombre de noeuds", len(noeuds) == 105, f"{len(noeuds)} noeuds")

    chemin = DATA / "noeuds.csv"
    if chemin.exists():
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            lignes = list(csv.DictReader(f))
        verdict("noeuds.csv synchronise avec la base",
                len(lignes) == len(noeuds), f"{len(lignes)} lignes")
    else:
        verdict("fichier noeuds.csv present", False)

    doublons = {}
    for n in noeuds:
        lat = champ(n, "latitude", "lat")
        lon = champ(n, "longitude", "lon", "lng")
        nom = champ(n, "nom", "libelle", "name") or "?"
        doublons.setdefault((round(float(lat), 6), round(float(lon), 6)), []).append(nom)
    collisions = {k: v for k, v in doublons.items() if len(v) > 1}
    verdict("aucune collision de coordonnees", len(collisions) == 0,
            f"{len(collisions)} collision(s)")
    for coord, noms in collisions.items():
        print(f"        {coord} : {', '.join(noms)}")

    return noeuds


# ---------------------------------------------------------------- maillon 4
def maillon_empreintes(noeuds):
    print("\n4. empreintes des matrices")
    attendue = svc.empreinte_noeuds(noeuds)
    print(f"        empreinte courante des noeuds : {attendue[:16]}...")

    for libelle, lecteur in (("geodesique", svc.lire_metadonnees),
                             ("routiere", svc.lire_metadonnees_routieres)):
        meta = lecteur()
        if not meta:
            verdict(f"metadonnees {libelle} lisibles", False, "fichier absent")
            continue
        stockee = meta.get("empreinte") or meta.get("empreinte_noeuds")
        verdict(f"cache {libelle} a jour", stockee == attendue,
                "valide" if stockee == attendue
                else "matrice perimee, regeneration necessaire")


# ---------------------------------------------------------------- maillon 5
def maillon_matrices():
    print("\n5. integrite numerique des matrices")
    for nom, symetrique in (("matrice_geodesique.npy", True),
                            ("matrice_routiere.npy", False)):
        chemin = DATA / nom
        if not chemin.exists():
            verdict(f"{nom} present", False)
            continue
        m = np.load(chemin)
        verdict(f"{nom} — dimensions", m.shape == (105, 105), str(m.shape))
        verdict(f"{nom} — diagonale nulle", bool(np.allclose(np.diag(m), 0)))

        hors_diag = m[~np.eye(m.shape[0], dtype=bool)]
        n_zeros = int((hors_diag == 0).sum())
        verdict(f"{nom} — aucun zero hors diagonale", n_zeros == 0,
                f"{n_zeros} zero(s)")
        verdict(f"{nom} — aucune valeur negative ou NaN",
                bool(np.isfinite(m).all() and (m >= 0).all()))

        if symetrique:
            verdict(f"{nom} — symetrie", bool(np.allclose(m, m.T, atol=1e-6)))
        else:
            ecart = float(np.abs(m - m.T).max())
            verdict(f"{nom} — asymetrie presente (D16)", ecart > 0,
                    f"ecart max {ecart:.1f} km")
        print(f"        min hors diagonale {hors_diag.min():.3f} km, "
              f"max {m.max():.1f} km, moyenne {hors_diag.mean():.1f} km")


# ---------------------------------------------------------------- execution
def main():
    print("=" * 66)
    print("CONTROLE DE COHERENCE — lecture seule")
    print("=" * 66)
    db = SessionLocal()
    try:
        maillon_stations_csv(db)
        maillon_seed(db)
        noeuds = maillon_noeuds(db)
    finally:
        db.close()
    maillon_empreintes(noeuds)
    maillon_matrices()

    print("\n" + "=" * 66)
    if anomalies:
        print(f"BILAN : {len(anomalies)} anomalie(s)")
        for a in anomalies:
            print(f"  - {a}")
        sys.exit(1)
    print("BILAN : chaine coherente, aucune anomalie detectee.")
    print("=" * 66)


if __name__ == "__main__":
    main()
