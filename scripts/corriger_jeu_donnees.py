"""calibrage du jeu de donnees.
1. Volumes des lots divises par 50 (changement d'unite).
2. Composition du parc : activation du 12, specialisation des 3 et 9.
Sauvegarde la base avant toute ecriture.
"""
import shutil
import sqlite3
from pathlib import Path

BASE = Path("livraison.db")
FACTEUR = 50

# id_vehicule -> (type_caisson, statut)
PARC = {
    12: ("refrigere", "actif"),   # etait en reserve
    3: ("refrigere", "actif"),   # etait standard
    9: ("securise", "actif"),    # etait standard
}

# --- sauvegarde ---------------------------------------------------------
sauvegarde = BASE.with_suffix(".db.bak")
shutil.copy(BASE, sauvegarde)
print(f"sauvegarde -> {sauvegarde}\n")

conn = sqlite3.connect(BASE)
cur = conn.cursor()

# --- 1. volumes ---------------------------------------------------------
avant = cur.execute("SELECT SUM(volume), MAX(volume) FROM lot").fetchone()
cur.execute("UPDATE lot SET volume = ROUND(volume / ?, 2)", (FACTEUR,))
apres = cur.execute("SELECT SUM(volume), MAX(volume) FROM lot").fetchone()
print(f"volumes : total {avant[0]:.2f} -> {apres[0]:.2f} | "
      f"max {avant[1]:.2f} -> {apres[1]:.2f}")

# --- 2. parc ------------------------------------------------------------
for id_v, (caisson, statut) in PARC.items():
    cur.execute(
        "UPDATE vehicule SET type_caisson=?, statut=? WHERE id_vehicule=?",
        (caisson, statut, id_v),
    )
    print(f"vehicule {id_v} -> {caisson}, {statut}")

conn.commit()

# --- 3. controles de coherence -----------------------------------------
print("\n--- controles ---")

capacite = cur.execute(
    "SELECT SUM(capacite) FROM vehicule WHERE statut='actif' AND assurance=1"
).fetchone()[0]
volume = cur.execute("SELECT SUM(volume) FROM lot").fetchone()[0]
print(f"capacite mobilisable : {capacite}")
print(f"volume total         : {volume:.2f}")
print(f"taux de remplissage  : {100 * volume / capacite:.1f} %")

lot_max = cur.execute("SELECT MAX(volume) FROM lot").fetchone()[0]
cap_min = cur.execute(
    "SELECT MIN(capacite) FROM vehicule WHERE statut='actif' AND assurance=1"
).fetchone()[0]
print(f"plus gros lot ({lot_max}) tient dans le plus petit vehicule ({cap_min}) : "
      f"{lot_max <= cap_min}")

# hypothese B : un caisson specialise sert aussi le standard
COUVRE = {"standard": {"standard"},
          "refrigere": {"refrigere", "standard"},
          "securise": {"securise", "standard"}}

dispo = cur.execute(
    "SELECT type_caisson, SUM(capacite), COUNT(*) FROM vehicule "
    "WHERE statut='actif' AND assurance=1 GROUP BY type_caisson"
).fetchall()

print("\nbesoin -> offre :")
for requis, nb_lots, vol_lots in cur.execute(
    "SELECT caisson_requis, COUNT(*), SUM(volume) FROM lot GROUP BY caisson_requis"
):
    veh = [(t, c, n) for t, c, n in dispo if requis in COUVRE[t]]
    cap = sum(c for _, c, _ in veh)
    nb_v = sum(n for _, _, n in veh)
    etat = "OK" if cap >= vol_lots else "INSUFFISANT"
    print(f"  {requis:10s} : {nb_lots:3d} lots, {vol_lots:7.2f} vol "
          f"-> {nb_v} vehicules, {cap} cap  [{etat}]")

nb_actifs = cur.execute(
    "SELECT COUNT(*) FROM vehicule WHERE statut='actif' AND assurance=1"
).fetchone()[0]
print(f"\nvehicules mobilisables : {nb_actifs}")

conn.close()
