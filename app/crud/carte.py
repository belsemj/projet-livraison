# app/crud/carte.py
from typing import Optional
from sqlalchemy.orm import Session, selectinload
from app.models.tournee import Tournee
from app.models.affectation import Affectation
from app.models.lot import Lot
from app.models.destination import Destination
from app.models.station import Station


def _coord(obj) -> dict:
    """Convertit lat/lon (Decimal en base) en float pour Folium/JSON."""
    return {"lat": float(obj.latitude), "lon": float(obj.longitude)}


def assembler_carte(db: Session, id_run: int) -> Optional[dict]:
    """Assemble toutes les donnees geo d'un run pour la cartographie.

    Socle unique : consomme par Folium aujourd'hui (Option A), expose
    en JSON pour Leaflet plus tard (Option B), sans retouche.

    Ne reutilise PAS lire_run() : le run de J2 est volontairement leger
    (D32, IDs seuls, aucune jointure). La carto fait sa propre requete
    avec chargement en profondeur tournee -> affectation -> lot ->
    destination. Deux endpoints, deux besoins, deux requetes.

    Code couleur destinations (D33-carto) :
      - vert  = servie dans ce run
      - rouge = lot present dans la vague du run mais non livree (abandonnee)
      - gris  = toute autre destination de la base (hors vague)
    Priorite si plusieurs lots sur une meme destination : vert > rouge > gris.

    Retourne None si aucune tournee ne porte cet id_run (-> 404 cote router).
    """
    tournees = (
        db.query(Tournee)
        .filter(Tournee.id_run == id_run)
        .options(
            selectinload(Tournee.affectations)
            .selectinload(Affectation.lot)
            .selectinload(Lot.destination),
            selectinload(Tournee.station_depart),
            selectinload(Tournee.station_retour),
        )
        .order_by(Tournee.id_tournee)
        .all()
    )
    if not tournees:
        return None

    # --- 1. Destinations SERVIES + vagues du run ---------------------------
    # On parcourt les lots reellement affectes : ils donnent a la fois les
    # destinations vertes et l'ensemble des vagues concernees par ce run.
    dest_servies = set()      # id_destination servis (vert)
    vagues = set()            # id_vague presents dans ce run
    for t in tournees:
        t.affectations.sort(key=lambda a: a.ordre_visite)
        for a in t.affectations:
            dest_servies.add(a.lot.id_destination)
            vagues.add(a.lot.id_vague)

    # --- 2. Destinations ATTENDUES de la/les vague(s) ----------------------
    # Tous les lots partageant un id_vague du run : leurs destinations sont
    # "attendues". Celles attendues mais non servies -> rouge (abandonnees).
    lots_vague = (
        db.query(Lot.id_destination)
        .filter(Lot.id_vague.in_(vagues))
        .distinct()
        .all()
    )
    dest_attendues = {row[0] for row in lots_vague}
    dest_abandonnees = dest_attendues - dest_servies

    # --- 3. Classement couleur de TOUTES les destinations ------------------
    # Priorite vert > rouge > gris appliquee par l'ordre des tests.
    toutes_dest = db.query(Destination).order_by(Destination.id_destination).all()
    destinations = []
    for d in toutes_dest:
        if d.id_destination in dest_servies:
            statut = "servie"          # vert
        elif d.id_destination in dest_abandonnees:
            statut = "abandonnee"      # rouge
        else:
            statut = "hors_vague"      # gris
        destinations.append({
            "id_destination": d.id_destination,
            "nom": d.nom,
            "gouvernorat": d.gouvernorat,
            "statut": statut,
            **_coord(d),
        })

    # --- 4. Depots : les 5 stations, contexte permanent --------------------
    stations = db.query(Station).order_by(Station.id_station).all()
    depots = [
        {"id_station": s.id_station, "nom": s.nom, **_coord(s)}
        for s in stations
    ]

    # --- 5. Tournees ordonnees : geometrie des polylignes ------------------
    tournees_geo = []
    for t in tournees:
        arrets = [
            {
                "ordre": a.ordre_visite,
                "id_lot": a.id_lot,
                "id_destination": a.lot.id_destination,
                "nom_dest": a.lot.destination.nom,
                **_coord(a.lot.destination),
            }
            for a in t.affectations
        ]
        tournees_geo.append({
            "id_tournee": t.id_tournee,
            "id_chauffeur": t.id_chauffeur,
            "id_vehicule": t.id_vehicule,
            "depot_depart": _coord(t.station_depart),
            "depot_retour": _coord(t.station_retour),
            "arrets": arrets,
        })

    return {
        "id_run": id_run,
        "depots": depots,
        "destinations": destinations,
        "tournees": tournees_geo,
    }
