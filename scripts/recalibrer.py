"""
Recalibrage de la limite de temps sur le probleme DECOMPOSE (S6 J1).

Le budget de 60 s a ete calibre au S5 J3 sur le probleme MONOLITHIQUE,
avant la contrainte de station source (S5 J4) qui decoupe le probleme en
cinq sous-problemes independants, plus faciles. Ce script rebalaie la
limite de temps sur la configuration de PRODUCTION (caissons + source
actifs, valeurs par defaut de resoudre) pour situer le plateau et, le cas
echeant, abaisser le defaut.

Ne touche pas a la base : construire_contexte lit une fois, resoudre ne
persiste rien (contrairement a POST /optimisations). Reutilise mesurer()
et ecrire() du harnais de reference pour un CSV tracable au meme format.

Usage (depuis la racine) :
    python -m scripts.recalibrer
"""

from app.database import SessionLocal
from app.services.matrice_etendue import construire_contexte, controler
from scripts.calibrer import mesurer, ecrire, RACINE

# Grille fine sous 60 s : on cherche le plancher a partir duquel la
# distance cesse de baisser (le plateau du probleme decompose).
LIMITES = [5, 10, 15, 20, 30, 45, 60]


def main() -> None:
    db = SessionLocal()
    try:
        ctx = construire_contexte(db)
    finally:
        db.close()

    # Les lignes [info] (depot sans porteur d'un caisson) ne sont pas
    # bloquantes ; toute autre anomalie l'est.
    bloquantes = [a for a in controler(ctx) if not a.startswith("[info]")]
    if bloquantes:
        print("ANOMALIES BLOQUANTES :")
        for a in bloquantes:
            print("  !", a)
        raise SystemExit(1)

    types = sorted({v.type_caisson for v in ctx.vehicules})
    print(f"contexte : {ctx.nb_noeuds} noeuds, {len(ctx.lots)} lots, "
          f"{ctx.nb_vehicules} vehicules ({', '.join(types)})")
    print("config production : caissons=True, source=True\n")

    lignes = []
    for limite in LIMITES:
        print(f"[recalibrage] limite={limite}s")
        # caissons et source restent a leur defaut (True) : configuration
        # exacte de POST /optimisations.
        lignes.append(mesurer(ctx, "recalibrage", limite_secondes=limite))

    chemin = ecrire("recalibrage", lignes)

    # Synthese : distance par limite et ecart relatif au meilleur point.
    best = min(l["distance_km"] for l in lignes)
    print("\n  limite   distance    ecart au min")
    for l in lignes:
        ecart = 100 * (l["distance_km"] - best) / best
        print(f"  {l['limite_s']:>4}s   {l['distance_km']:8.1f}   +{ecart:4.1f} %")
    print(f"\n{len(lignes)} mesures -> {chemin.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
