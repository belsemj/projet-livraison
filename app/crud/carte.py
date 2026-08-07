# app/crud/carte.py
from typing import Optional
from sqlalchemy.orm import Session, selectinload
from app.models.tournee import Tournee
from app.models.affectation import Affectation
from app.models.lot import Lot
from app.models.destination import Destination
from app.models.station import Station
from app.models.lot_non_servi import LotNonServi as LotNonServiRow


def _coord(obj) -> dict:
    """Convertit lat/lon (Decimal en base) en float pour Folium/JSON."""
    return {"lat": float(obj.latitude), "lon": float(obj.longitude)}


def assembler_carte(db: Session, id_run: int) -> Optional[dict]:
    """Assemble toutes les donnees geo d'un run pour la cartographie.

    Socle unique : consomme par Folium (Option A), expose
    en JSON pour Leaflet (Option B), sans retouche.

    Ne reutilise PAS lire_run() : chargement en profondeur propre a la carto
    (tournee -> affectation -> lot -> destination). Deux endpoints, deux
    besoins, deux requetes.

    Code couleur destinations:
      - rouge = destination ayant AU MOINS un lot non servi dans ce run
      - vert  = destination servie (et sans lot non servi)
      - gris  = toute autre destination de la base

    Priorite : ROUGE > vert > gris. L'abandon n'est JAMAIS masque par un lot
    servi sur la meme destination. C'est la revision de la priorite
    (vert > rouge) qui, quand un lot etait servi et un autre abandonne sur la
    meme destination, affichait vert et cachait l'abandon -> divergence carte
    vs resume. On lit maintenant le FAIT persiste (table lot_non_servi), plus
    une inference "vague moins servis" au niveau destination.

    Chaque destination porte 'lots_non_servis' : [{id_lot, raison}] (vide si
    aucun), pour le popup.

    Retourne None si le run n'existe pas (ni tournee ni lot non servi).
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

    # Lots non servis PERSISTES pour ce run (fait, non infere). Chaque ligne
    # porte id_lot + raison ; on joint Lot pour la destination a colorer.
    lns_rows = (
        db.query(LotNonServiRow.id_lot, LotNonServiRow.raison, Lot.id_destination)
        .join(Lot, LotNonServiRow.id_lot == Lot.id_lot)
        .filter(LotNonServiRow.id_run == id_run)
        .all()
    )

    # Un run peut n'avoir aucune tournee et pourtant exister par ses lots non
    # servis (cas extreme : tout abandonne). Inexistant seulement si les deux
    # sont vides (-> 404 cote router).
    if not tournees and not lns_rows:
        return None

    # --- 1. Destinations SERVIES (via affectations reelles) ----------------
    dest_servies = set()
    for t in tournees:
        t.affectations.sort(key=lambda a: a.ordre_visite)
        for a in t.affectations:
            dest_servies.add(a.lot.id_destination)

    # --- 2. Destinations ABANDONNEES (fait persiste) + detail par dest -----
    dest_abandonnees: set[int] = set()
    non_servis_par_dest: dict[int, list[dict]] = {}
    for id_lot, raison, id_dest in lns_rows:
        dest_abandonnees.add(id_dest)
        non_servis_par_dest.setdefault(id_dest, []).append(
            {"id_lot": id_lot, "raison": raison}
        )

    # --- 3. Classement couleur de TOUTES les destinations ------------------
    # Priorite ROUGE > vert > gris appliquee par l'ordre des tests.
    toutes_dest = db.query(Destination).order_by(Destination.id_destination).all()
    destinations = []
    for d in toutes_dest:
        if d.id_destination in dest_abandonnees:
            statut = "abandonnee"      # rouge (prioritaire)
        elif d.id_destination in dest_servies:
            statut = "servie"          # vert
        else:
            statut = "hors_vague"      # gris (clef conservee ; = "autre")
        destinations.append({
            "id_destination": d.id_destination,
            "nom": d.nom,
            "gouvernorat": d.gouvernorat,
            "statut": statut,
            "lots_non_servis": non_servis_par_dest.get(d.id_destination, []),
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
