"""
CRUD de la vague (S7) : insertion d'un ensemble de lots sous un id_vague.

Le commit est du ressort du routeur (comme partout ailleurs) ; ici on prepare
les objets et on flush pour obtenir les identifiants generes.
"""

from datetime import datetime

from app.models.lot import Lot
from app.schemas.vague import VagueRequete


def prochain_id_vague(db) -> str:
    """
    id_vague lisible et sans collision : horodatage a la microseconde.

    Format 'vague_AAAAMMJJ_HHMMSS_ffffff' (28 caracteres, sous la limite de 30
    de la colonne). Deux vagues creees dans la meme seconde restent distinctes.
    """
    return "vague_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def creer_vague(db, requete: VagueRequete) -> tuple[str, list[int]]:
    """
    Cree tous les lots de la vague. Ne commit pas : le routeur s'en charge,
    apres validation des cles etrangeres.

    Renvoie (id_vague, [id_lot...]) dans l'ordre de saisie.
    """
    id_vague = requete.id_vague or prochain_id_vague(db)

    objets: list[Lot] = []
    for entree in requete.lots:
        lot = Lot(
            volume=entree.volume,
            caisson_requis=entree.caisson_requis,
            id_destination=entree.id_destination,
            id_station_source=entree.id_station_source,
            priorite=entree.priorite,
            fragile=entree.fragile,
            id_vague=id_vague,
        )
        db.add(lot)
        objets.append(lot)

    db.flush()  # attribue les id_lot sans clore la transaction
    return id_vague, [lot.id_lot for lot in objets]
