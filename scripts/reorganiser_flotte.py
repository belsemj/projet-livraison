"""
Reorganisation de la flotte — D33 (S5 J4).

ECRIT EN BASE. Sauvegarde `livraison.db` avant toute modification.

Objet : passer d'une flotte concentree (tout le refrigere au depot 3, tout le
securise au depot 4) a une flotte repartie : un vehicule standard et un
refrigere par depot, plus un unique vehicule securise au depot 1.

Seuls `id_station` et `type_caisson` changent. Aucune capacite n'est modifiee :
le multiensemble des capacites est conserve a l'identique, c'est la meme flotte
redeployee. Cette propriete est verifiee avant et apres ecriture.

Le depot 1 recoit le vehicule securise parce que la capacite l'impose : il
concentre 40,13 m3 de standard et de refrigere, et ses deux plus gros porteurs
possibles plafonnent a 40,00 m3. Sous l'hypothese B un caisson securise
transporte aussi du standard, donc ce troisieme vehicule soulage reellement.

Ce placement est un artefact de jeu de test, de meme nature que D15. Il n'a
pas ete valide par M. Zghili et doit etre presente comme tel.

Invocation (depuis la racine du projet) :
    python -m scripts.reorganiser_flotte           # simulation, aucune ecriture
    python -m scripts.reorganiser_flotte --ecrire  # applique
"""

import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.services.matrice_etendue import charger_flotte
from app.models.vehicule import Vehicule


# ---------------------------------------------------------------------------
# Cible D33 : id_vehicule -> (id_station, type_caisson)
# ---------------------------------------------------------------------------

CIBLE: dict[int, tuple[int, str]] = {
    6:  (1, "standard"),
    12: (1, "refrigere"),
    9:  (1, "securise"),
    7:  (2, "standard"),
    8:  (2, "refrigere"),
    3:  (3, "standard"),
    2:  (3, "refrigere"),
    10: (4, "standard"),
    1:  (4, "refrigere"),
    5:  (5, "standard"),
    4:  (5, "refrigere"),
}

# Etat attendu AVANT ecriture. Si la base ne correspond pas, on refuse d'ecrire
# plutot que d'appliquer une cible calculee sur d'autres donnees.
ATTENDU_AVANT: dict[int, tuple[int, str]] = {
    1:  (1, "standard"),
    6:  (1, "standard"),
    2:  (2, "standard"),
    7:  (2, "standard"),
    3:  (3, "refrigere"),
    8:  (3, "standard"),
    12: (3, "refrigere"),
    4:  (4, "standard"),
    9:  (4, "securise"),
    5:  (5, "standard"),
    10: (5, "standard"),
}

CHEMIN_BASE = Path("livraison.db")


def _attribut(objet, candidats: list[str], etiquette: str) -> str:
    for nom in candidats:
        if hasattr(objet, nom):
            return nom
    raise SystemExit(
        f"Attribut {etiquette} introuvable sur {type(objet).__name__} "
        f"(essayes : {', '.join(candidats)})."
    )


def ouvrir_session():
    erreurs = []
    for module, fabrique in [
        ("app.database", "SessionLocal"),
        ("app.db.session", "SessionLocal"),
        ("app.db", "SessionLocal"),
        ("app.core.database", "SessionLocal"),
    ]:
        try:
            mod = __import__(module, fromlist=[fabrique])
            return getattr(mod, fabrique)()
        except (ImportError, AttributeError) as exc:
            erreurs.append(f"  {module}.{fabrique} : {exc}")
    raise SystemExit("Impossible d'ouvrir une session.\n" + "\n".join(erreurs))


def ligne(largeur: int = 74) -> None:
    print("-" * largeur)


def etat(flotte, nom_cap: str) -> dict[int, tuple[int, str, float]]:
    return {
        v.id_vehicule: (v.id_station, v.type_caisson, float(getattr(v, nom_cap)))
        for v in flotte
    }


def afficher_par_depot(courant: dict[int, tuple[int, str, float]]) -> None:
    par_depot = defaultdict(list)
    for id_v, (station, caisson, cap) in courant.items():
        par_depot[station].append((id_v, caisson, cap))
    for s in sorted(par_depot):
        detail = ", ".join(
            f"#{i} {c} ({cap:.2f})" for i, c, cap in sorted(par_depot[s])
        )
        total = sum(cap for _, _, cap in par_depot[s])
        print(f"  Depot {s} : {detail}   [total {total:.2f}]")


def main() -> None:
    ecrire = "--ecrire" in sys.argv

    db = ouvrir_session()
    try:
        flotte = charger_flotte(db)
        if not flotte:
            raise SystemExit("Flotte mobilisable vide (D23).")

        nom_cap = _attribut(flotte[0], ["capacite", "capacite_m3",
                                        "capacite_volume"], "capacite")
        avant = etat(flotte, nom_cap)

        print()
        ligne()
        print("REORGANISATION DE LA FLOTTE — D33")
        print("MODE SIMULATION (aucune ecriture)" if not ecrire
              else "MODE ECRITURE")
        ligne()

        # --- Controle 1 : la flotte est bien celle attendue -----------------
        reel = {i: (s, c) for i, (s, c, _) in avant.items()}
        if reel != ATTENDU_AVANT:
            print("ETAT INATTENDU — ecriture refusee.")
            print()
            print("Ecarts (id : trouve / attendu) :")
            for id_v in sorted(set(reel) | set(ATTENDU_AVANT)):
                r = reel.get(id_v, "absent")
                a = ATTENDU_AVANT.get(id_v, "absent")
                if r != a:
                    print(f"  #{id_v} : {r} / {a}")
            print()
            print("La cible D33 a ete calculee sur l'etat du diagnostic.")
            print("Relance scripts/diag_station_source.py et previens-moi.")
            raise SystemExit(1)

        # --- Controle 2 : conservation des capacites ------------------------
        caps_avant = sorted(cap for _, _, cap in avant.values())
        if set(CIBLE) != set(avant):
            raise SystemExit("La cible ne couvre pas exactement la flotte.")

        print("Etat AVANT :")
        afficher_par_depot(avant)

        apres = {
            i: (CIBLE[i][0], CIBLE[i][1], avant[i][2]) for i in avant
        }
        print()
        print("Etat APRES :")
        afficher_par_depot(apres)

        caps_apres = sorted(cap for _, _, cap in apres.values())
        if caps_avant != caps_apres:
            raise SystemExit("Les capacites ne sont pas conservees — abandon.")
        print()
        print(f"Capacites conservees : {caps_avant}")

        # --- Controle 3 : un standard et un refrigere par depot -------------
        par_depot = defaultdict(list)
        for _, (s, c, _) in apres.items():
            par_depot[s].append(c)
        anomalies = []
        for s in range(1, 6):
            types = par_depot.get(s, [])
            if types.count("standard") != 1 or types.count("refrigere") != 1:
                anomalies.append(f"depot {s} : {sorted(types)}")
        nb_securise = sum(1 for _, (_, c, _) in apres.items() if c == "securise")
        if nb_securise != 1:
            anomalies.append(f"{nb_securise} vehicule(s) securise(s), attendu 1")
        if anomalies:
            raise SystemExit("Cible incoherente : " + " ; ".join(anomalies))
        print("Structure cible verifiee : 1 standard + 1 refrigere par depot,")
        print("1 securise unique.")

        # --- Modifications a appliquer --------------------------------------
        changements = [
            (i, avant[i][:2], CIBLE[i]) for i in sorted(avant)
            if avant[i][:2] != CIBLE[i]
        ]
        print()
        ligne()
        print(f"{len(changements)} vehicule(s) modifie(s), "
              f"{len(avant) - len(changements)} inchange(s)")
        ligne()
        for id_v, (sa, ca), (sc, cc) in changements:
            marque = []
            if sa != sc:
                marque.append(f"depot {sa} -> {sc}")
            if ca != cc:
                marque.append(f"{ca} -> {cc}")
            print(f"  #{id_v:<3} " + " | ".join(marque))

        if not ecrire:
            print()
            print("Simulation terminee. Rien n'a ete ecrit.")
            print("Relance avec --ecrire pour appliquer.")
            return

        # --- Sauvegarde ------------------------------------------------------
        if not CHEMIN_BASE.exists():
            raise SystemExit(
                f"Base introuvable a '{CHEMIN_BASE}'. Lance le script depuis "
                "la racine du projet."
            )
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        sauvegarde = CHEMIN_BASE.with_suffix(f".db.{horodatage}.bak")
        shutil.copy2(CHEMIN_BASE, sauvegarde)
        print()
        print(f"Sauvegarde : {sauvegarde}")

        # --- Ecriture --------------------------------------------------------
        for id_v, (station, caisson) in CIBLE.items():
            v = db.query(Vehicule).filter(
                Vehicule.id_vehicule == id_v
            ).one()
            v.id_station = station
            v.type_caisson = caisson
        db.commit()
        print("Ecriture effectuee.")

    finally:
        db.close()

    # --- Verification sur session neuve --------------------------------------
    db2 = ouvrir_session()
    try:
        relu = etat(charger_flotte(db2), nom_cap)
    finally:
        db2.close()

    print()
    ligne()
    print("VERIFICATION (relecture sur session neuve)")
    ligne()
    afficher_par_depot(relu)

    attendu = {i: (CIBLE[i][0], CIBLE[i][1], avant[i][2]) for i in avant}
    if relu == attendu:
        print()
        print("Conforme a la cible D33.")
        print()
        print("Prochaines etapes :")
        print("  - propager vers data/seed.sql (sinon une reconstruction")
        print("    depuis zero perdrait D33)")
        print("  - migration Alembic : id_station_source + id_vague sur lot")
        print("  - relancer scripts/diag_station_source.py")
    else:
        print()
        print("ECART APRES ECRITURE — restaure la sauvegarde et previens-moi.")
        for i in sorted(set(relu) | set(attendu)):
            if relu.get(i) != attendu.get(i):
                print(f"  #{i} : {relu.get(i)} / attendu {attendu.get(i)}")


if __name__ == "__main__":
    main()
