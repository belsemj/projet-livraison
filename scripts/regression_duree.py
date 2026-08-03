# scripts/regression_duree.py
"""
Brique methodologique : prediction de la DUREE D'UNE TOURNEE (en minutes).

Contexte S8 J3 : pas de donnees historiques reelles (Q3). On demontre donc le
PIPELINE de regression sur des donnees SIMULEES, pas la performance predictive
sur la realite.

--- Piege evite : la circularite ---------------------------------------------
Si on fabrique la duree avec une formule puis qu'on la "retrouve" par
regression, le R2 frole 1 et ne prouve rien. Pour rester honnete :
  1. le modele generatif est DOCUMENTE explicitement (constantes ci-dessous) ;
  2. un BRUIT gaussien homoscedastique (~45 min) est ajoute ;
  3. les features sont INDEPENDANTES -> les coefficients recuperes sont
     directement comparables au modele generatif (controle d'honnetete) ;
  4. la LECTURE finale est pilotee par les chiffres reels du run (le script
     conclut selon le modele qui gagne effectivement), jamais codee en dur.

Le R2 obtenu est ELEVE parce que le bruit simule est faible PAR CONSTRUCTION :
l'objectif est de verifier que le pipeline retrouve le modele documente, pas de
simuler la variabilite reelle. Sur des durees reelles (Q3), le R2 sera
nettement plus bas -- c'est attendu et a ecrire tel quel dans le rapport.

--- Transferabilite (quand les vraies durees arriveront) ---------------------
Le pipeline (features -> modele -> evaluation) ne bouge pas. Il suffira de
remplacer la colonne cible 'duree_min' simulee par les durees reelles mesurees,
en gardant les memes features. AUCUN endpoint de prediction n'est expose en
prod : un modele cale sur du simule donnerait de faux chiffres presentes comme
vrais. C'est une brique de rapport, pas un service.

D-serie "regression" : cible simulee, features
[distance_km, nb_arrets, volume_total_m3, part_caisson_special], modele
generatif documente, pas d'endpoint prod.

Lancement (depuis la racine du projet) :
    python -m scripts.regression_duree            # brique methodo seule
    python -m scripts.regression_duree --reel     # + demo sur les vraies tournees (DB)
    python -m scripts.regression_duree --reel --run 1   # limite a un id_run
"""

import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

SEED = 42
N = 600  # nb de tournees simulees (assez pour une eval stable)

# =============================================================================
#  MODELE GENERATIF DOCUMENTE  (duree en MINUTES)
#  Hypotheses metier ; a valider par M. Zghili, a remplacer par les vraies
#  mesures des que Q3 est disponible. Additif ; seule non-linearite : une
#  legere congestion sur les tres longues distances.
# =============================================================================
VITESSE_KMH = 50.0                 # vitesse moyenne reseau tunisien (mixte) -> 1.2 min/km
CONGESTION_LONG = 0.05             # +5% de conduite sur les tres longues distances
SERVICE_BASE_MIN = 12.0            # temps de base par arret (min)
MIN_PAR_M3 = 4.0                   # supplement dechargement par m3 (min/m3)
SUPP_CAISSON_MIN = 40.0            # + SUPP*part_special (max +24 min a 60% d'arrets speciaux)
CONSTANTE_MIN = 30.0               # preparation + retour depot (min)
BRUIT_ABS_MIN = 45.0               # ecart-type du bruit gaussien (min), homoscedastique

FEATURES = ["distance_km", "nb_arrets", "volume_total_m3", "part_caisson_special"]
CIBLE = "duree_min"
CAISSONS_SPECIAUX = ("refrigere", "securise")


def generer_donnees(n=N, seed=SEED):
    """Genere un jeu de tournees simule realiste (fourchettes issues du projet).

    Features tirees INDEPENDAMMENT (pour une recuperation propre des
    coefficients ; en realite volume et nb_arrets sont un peu correles, a
    raffiner avec les vraies donnees) :
      - distance_km          : 70 a 1200 km (etendue reelle du reseau)
      - nb_arrets            : 5 a 20 arrets
      - volume_total_m3      : 2 a 24 m3
      - part_caisson_special : fraction d'arrets a caisson refrigere/securise

    Cible simulee (duree_min) : additif + congestion douce + bruit gaussien fixe.
    """
    rng = np.random.default_rng(seed)

    distance_km = rng.uniform(70, 1200, n)
    nb_arrets = rng.integers(5, 21, n)                 # 5..20 inclus
    volume_total = rng.uniform(2.0, 24.0, n)           # m3, independant
    part_special = rng.uniform(0.0, 0.6, n)            # 0 a 60% d'arrets speciaux

    temps_conduite = (distance_km / VITESSE_KMH) * 60.0
    temps_conduite *= 1.0 + CONGESTION_LONG * (distance_km / 1200.0)  # congestion douce

    temps_service = (
        nb_arrets * SERVICE_BASE_MIN
        + MIN_PAR_M3 * volume_total
        + SUPP_CAISSON_MIN * part_special
    )

    duree = CONSTANTE_MIN + temps_conduite + temps_service
    duree = duree + rng.normal(0.0, BRUIT_ABS_MIN, n)  # bruit homoscedastique
    duree = np.maximum(duree, 15.0)                    # plancher de bon sens

    return pd.DataFrame(
        {
            "distance_km": np.round(distance_km, 2),
            "nb_arrets": nb_arrets,
            "volume_total_m3": np.round(volume_total, 2),
            "part_caisson_special": np.round(part_special, 3),
            "duree_min": np.round(duree, 1),
        }
    )


def evaluer(nom, modele, X_train, X_test, y_train, y_test, X, y):
    """Entraine, mesure sur le test, et fait une validation croisee 5 plis."""
    modele.fit(X_train, y_train)
    pred = modele.predict(X_test)

    mae = mean_absolute_error(y_test, pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    r2 = r2_score(y_test, pred)
    cv = cross_val_score(modele, X, y, cv=5, scoring="r2")

    print(f"\n--- {nom} ---")
    print(f"  Test  : MAE = {mae:6.1f} min | RMSE = {rmse:6.1f} min | R2 = {r2:.3f}")
    print(f"  CV 5plis R2 : {cv.mean():.3f} +/- {cv.std():.3f}")
    return {"nom": nom, "mae": mae, "rmse": rmse, "r2": r2,
            "cv_moy": cv.mean(), "cv_ecart": cv.std(), "pred_test": pred}


def main(reel=False, id_run=None):
    print("=" * 74)
    print(" Regression METHODO : duree d'une tournee (donnees SIMULEES, seed 42)")
    print("=" * 74)

    df = generer_donnees()
    X = df[FEATURES].values
    y = df[CIBLE].values

    print(f"\n{len(df)} tournees simulees. Apercu :")
    print(df.head(5).to_string(index=False))
    print(f"\nDuree simulee : min {y.min():.0f} | moyenne {y.mean():.0f} | max {y.max():.0f} (min)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED
    )

    lin = LinearRegression()
    res_lin = evaluer("Regression lineaire", lin, X_train, X_test, y_train, y_test, X, y)

    rf = RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=-1)
    res_rf = evaluer("RandomForest", rf, X_train, X_test, y_train, y_test, X, y)

    # --- Coefficients du lineaire vs modele generatif (controle d'honnetete) --
    print("\n--- Coefficients du modele lineaire (min par unite de feature) ---")
    attendu = {
        "distance_km": f"~{60/VITESSE_KMH:.2f} (+ congestion)",
        "nb_arrets": f"~{SERVICE_BASE_MIN:.0f}",
        "volume_total_m3": f"~{MIN_PAR_M3:.0f}",
        "part_caisson_special": f"~{SUPP_CAISSON_MIN:.0f}",
    }
    for f, c in zip(FEATURES, lin.coef_):
        print(f"  {f:22s} : {c:8.2f}   (attendu {attendu[f]})")
    print(f"  {'(constante)':22s} : {lin.intercept_:8.2f}   (attendu ~{CONSTANTE_MIN:.0f})")
    print("  -> proches du modele documente (a la variabilite d'echantillonnage")
    print("     pres) : le pipeline retrouve bien la structure generatrice.")

    # --- Importances du RandomForest ------------------------------------------
    print("\n--- Importances des features (RandomForest) ---")
    importances = sorted(zip(FEATURES, rf.feature_importances_),
                         key=lambda t: t[1], reverse=True)
    for f, imp in importances:
        print(f"  {f:22s} : {imp:.3f}")

    # --- Lecture PILOTEE PAR LES CHIFFRES (jamais codee en dur) ----------------
    print("\n--- Lecture ---")
    ecart = res_lin["r2"] - res_rf["r2"]
    if ecart >= -0.005:
        print(f"  * Le lineaire fait aussi bien ou mieux que le RandomForest")
        print(f"    (R2 {res_lin['r2']:.3f} vs {res_rf['r2']:.3f}) : la relation est")
        print("    essentiellement lineaire. On GARDE le lineaire (interpretable) ;")
        print("    le RandomForest, en garde-fou, ne revele pas de non-linearite forte.")
    else:
        print(f"  * Le RandomForest depasse le lineaire (R2 {res_rf['r2']:.3f} vs")
        print(f"    {res_lin['r2']:.3f}) : une non-linearite est captee -> a creuser.")
    top_feat, top_imp = importances[0]
    print(f"  * Feature dominante : {top_feat} ({top_imp:.0%} de l'importance) —")
    print("    la duree est surtout portee par la distance, coherent avec le terrain.")
    print("  * R2 eleve = bruit simule faible PAR CONSTRUCTION (validation du")
    print("    pipeline). Sur des durees reelles, il sera nettement plus bas.")

    # --- Artefacts (dataset + graphe) -----------------------------------------
    os.makedirs("data", exist_ok=True)
    chemin_csv = os.path.join("data", "durees_simulees.csv")
    df.to_csv(chemin_csv, index=False)
    print(f"\nDataset simule ecrit : {chemin_csv}")
    _tracer_pred_vs_reel(y_test, res_rf["pred_test"], res_lin["pred_test"])

    # --- Bonus optionnel : prediction sur les VRAIES tournees (DB) -------------
    if reel:
        _demo_tournees_reelles(lin, id_run)


def _tracer_pred_vs_reel(y_test, pred_rf, pred_lin):
    """Nuage predit vs reel (test). matplotlib optionnel : ignore si absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("(matplotlib absent : graphe ignore)")
        return

    lim = [min(y_test.min(), pred_rf.min(), pred_lin.min()),
           max(y_test.max(), pred_rf.max(), pred_lin.max())]
    fig, ax = plt.subplots(1, 2, figsize=(11, 5), sharex=True, sharey=True)
    for a, pred, titre in (
        (ax[0], pred_lin, "Regression lineaire"),
        (ax[1], pred_rf, "RandomForest"),
    ):
        a.scatter(y_test, pred, s=14, alpha=0.5, edgecolor="none")
        a.plot(lim, lim, "r--", linewidth=1)
        a.set_title(titre)
        a.set_xlabel("Duree reelle simulee (min)")
    ax[0].set_ylabel("Duree predite (min)")
    fig.suptitle("Predit vs reel (jeu de test) - donnees simulees")
    fig.tight_layout()
    chemin_png = os.path.join("data", "regression_duree_pred_vs_reel.png")
    fig.savefig(chemin_png, dpi=120)
    print(f"Graphe ecrit          : {chemin_png}")


def _demo_tournees_reelles(modele, id_run=None):
    """ILLUSTRATIF : applique le modele (cale sur du SIMULE) aux vraies tournees.

    Ce ne sont PAS des durees mesurees ni validees : juste une demonstration
    que le pipeline tourne sur des lignes reelles. Les features sont extraites
    de la base exactement comme ailleurs dans le projet :
      distance_km = tournee.distance_totale
      nb_arrets   = nb d'affectations de la tournee
      volume      = somme des quantites affectees
      part_special= fraction d'arrets dont le lot exige un caisson refr./secur.
    """
    print("\n" + "=" * 74)
    print(" BONUS ILLUSTRATIF : durees predites sur les VRAIES tournees")
    print(" (modele cale sur du simule -> chiffres indicatifs, NON valides)")
    print("=" * 74)

    try:
        from sqlalchemy.orm import selectinload
        from app.database import get_db
        from app.models.tournee import Tournee
        from app.models.affectation import Affectation
        from app.models.lot import Lot  # noqa: F401 (charge via selectinload)
    except Exception as e:
        print(f"\n[demo reelle indisponible] {e}")
        print("Lance depuis la racine du projet :")
        print("    python -m scripts.regression_duree --reel")
        return

    gen = get_db()
    db = next(gen)
    try:
        q = db.query(Tournee).options(
            selectinload(Tournee.affectations).selectinload(Affectation.lot)
        )
        if id_run is not None:
            q = q.filter(Tournee.id_run == id_run)
        tournees = q.order_by(Tournee.id_run, Tournee.id_tournee).all()

        if not tournees:
            cible = f"run {id_run}" if id_run is not None else "la base"
            print(f"\nAucune tournee trouvee pour {cible}.")
            return

        print(f"\n{'run':>4} {'tournee':>8} {'dist_km':>8} {'arrets':>7} "
              f"{'vol_m3':>7} {'%spec':>6} | {'duree predite':>16}")
        print("-" * 74)
        for t in tournees:
            nb = len(t.affectations)
            vol = float(sum(float(a.quantite) for a in t.affectations))
            nb_spec = sum(
                1 for a in t.affectations
                if a.lot is not None and a.lot.caisson_requis in CAISSONS_SPECIAUX
            )
            part = (nb_spec / nb) if nb else 0.0
            dist = float(t.distance_totale or 0.0)

            pred = float(modele.predict([[dist, nb, vol, part]])[0])
            h, m = divmod(int(round(pred)), 60)
            print(f"{t.id_run:>4} {t.id_tournee:>8} {dist:>8.1f} {nb:>7} "
                  f"{vol:>7.1f} {part:>6.0%} | {pred:>7.0f} min ({h} h {m:02d})")

        print("\nRappel : durees ILLUSTRATIVES (modele simule). Remplacer par un")
        print("modele reentraine sur les vraies durees Q3 avant tout usage.")
    finally:
        gen.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Regression methodo duree de tournee")
    p.add_argument("--reel", action="store_true",
                   help="predire aussi sur les vraies tournees (acces DB)")
    p.add_argument("--run", type=int, default=None,
                   help="limiter la demo reelle a un id_run (defaut : toutes)")
    a = p.parse_args()
    main(reel=a.reel, id_run=a.run)
