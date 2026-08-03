# app/services/carte_folium.py
import folium

# Centre approximatif de la Tunisie + zoom pays entier
CENTRE_TUNISIE = (34.5, 9.5)
ZOOM_INITIAL = 7

# Couleurs des destinations (D33-carto)
COULEUR_STATUT = {
    "servie": "#2e7d32",       # vert
    "abandonnee": "#c62828",   # rouge
    "hors_vague": "#9e9e9e",   # gris
}
LIBELLE_STATUT = {
    "servie": "Servie",
    "abandonnee": "Non livree (au moins un lot abandonne)",
    "hors_vague": "Autre destination",
}

# Libelles lisibles des raisons d'abandon (miroir des valeurs solveur).
LIBELLE_RAISON = {
    "abandon_solveur": "aucun vehicule compatible",
    "capacite_locale": "capacite locale insuffisante",
    "echec_solveur": "echec du solveur",
}

# Palette 9 couleurs pour les tournees. Choisies distinctes du vert/rouge/gris
# des destinations pour ne pas confondre les traces avec les statuts.
PALETTE_TOURNEES = [
    "#1f77b4",  # bleu
    "#ff7f0e",  # orange
    "#9467bd",  # violet
    "#8c564b",  # brun
    "#e377c2",  # rose
    "#17becf",  # cyan
    "#bcbd22",  # olive
    "#008080",  # sarcelle
    "#ff1493",  # magenta
]

# Palette 7 zones geographiques (D-serie zonage). Qualitative, distincte du
# vert/rouge/gris des statuts. Numerotation nord->sud (cf. clustering.py).
PALETTE_ZONES = {
    1: "#6a51a3",  # Grand Tunis  - violet
    2: "#2171b5",  # Nord-Ouest   - bleu
    3: "#238b8b",  # Sahel        - teal
    4: "#d9a300",  # Centre       - or
    5: "#cc6600",  # Sfax         - orange brule
    6: "#c51b7d",  # Djerid       - magenta
    7: "#8c510a",  # Sud-Est      - brun
}
# Libelles lisibles des zones (interpretation stable a k=7, ordre nord->sud).
NOM_ZONE = {
    1: "Grand Tunis", 2: "Nord-Ouest", 3: "Sahel", 4: "Centre",
    5: "Sfax", 6: "Djerid", 7: "Sud-Est",
}


def _popup_abandon(dest: dict) -> folium.Popup | None:
    """Popup listant les lots non livres d'une destination + leur raison.

    None si la destination n'a aucun lot abandonne (pas de popup superflu).
    """
    lots = dest.get("lots_non_servis") or []
    if not lots:
        return None
    lignes = "".join(
        f"<li>Lot {l['id_lot']} : {LIBELLE_RAISON.get(l['raison'], l['raison'])}</li>"
        for l in lots
    )
    html = (
        f"<b>{dest['nom']}</b> ({dest['gouvernorat']})<br>"
        f"Lot(s) non livre(s) :<ul style='margin:4px 0 0 16px;padding:0;'>{lignes}</ul>"
    )
    return folium.Popup(html, max_width=280)


def rendre_carte_html(data: dict) -> str:
    """Produit une page HTML Folium autonome a partir de la structure
    assemblee par app.crud.carte.assembler_carte(), enrichie du zonage.

    Socle Option A : cette fonction rend du HTML pret a embarquer. La meme
    structure 'data' sert de JSON a Leaflet en Option B, sans y toucher.
    """
    m = folium.Map(location=CENTRE_TUNISIE, zoom_start=ZOOM_INITIAL,
                   tiles="OpenStreetMap")

    # --- Depots : 5 reperes distincts (icone maison noire) -----------------
    grp_depots = folium.FeatureGroup(name="Depots (5)", show=True)
    for d in data["depots"]:
        folium.Marker(
            location=(d["lat"], d["lon"]),
            tooltip=f"Depot : {d['nom']}",
            icon=folium.Icon(color="black", icon="home", prefix="fa"),
        ).add_to(grp_depots)
    grp_depots.add_to(m)

    # --- Destinations : 3 groupes toggables par statut ---------------------
    groupes_dest = {
        "servie": folium.FeatureGroup(name="Destinations servies", show=True),
        "abandonnee": folium.FeatureGroup(name="Destinations non livrees", show=True),
        "hors_vague": folium.FeatureGroup(name="Autres destinations", show=False),
    }
    for dest in data["destinations"]:
        statut = dest["statut"]
        folium.CircleMarker(
            location=(dest["lat"], dest["lon"]),
            radius=5,
            color=COULEUR_STATUT[statut],
            fill=True,
            fill_color=COULEUR_STATUT[statut],
            fill_opacity=0.9,
            tooltip=f"{dest['nom']} ({dest['gouvernorat']}) - {LIBELLE_STATUT[statut]}",
            popup=_popup_abandon(dest),   # None sauf si lots non livres
        ).add_to(groupes_dest[statut])
    for g in groupes_dest.values():
        g.add_to(m)

    # --- Zones ML : calque analytique SEPARE (D-serie zonage) --------------
    # Memes 100 destinations, mais colorees par zone geographique au lieu du
    # statut. Decoche par defaut : c'est une lecture geographique, pas l'etat
    # du run. Aucune interaction avec les groupes de statut ci-dessus.
    grp_zones = folium.FeatureGroup(name="Zones geographiques (7)", show=False)
    for dest in data["destinations"]:
        z = dest.get("id_zone")
        if z is None:
            continue
        couleur = PALETTE_ZONES.get(z, "#000000")
        folium.CircleMarker(
            location=(dest["lat"], dest["lon"]),
            radius=6,
            color=couleur,
            fill=True,
            fill_color=couleur,
            fill_opacity=0.85,
            tooltip=f"{dest['nom']} - Zone {z} ({NOM_ZONE.get(z, '?')})",
        ).add_to(grp_zones)
    grp_zones.add_to(m)

    # --- Tournees : une polyligne par tournee, ordre de passage ------------
    # Trace = depot_depart -> arret1 -> ... -> arretN -> depot_retour.
    for i, t in enumerate(data["tournees"]):
        couleur = PALETTE_TOURNEES[i % len(PALETTE_TOURNEES)]
        points = [(t["depot_depart"]["lat"], t["depot_depart"]["lon"])]
        points += [(a["lat"], a["lon"]) for a in t["arrets"]]
        points.append((t["depot_retour"]["lat"], t["depot_retour"]["lon"]))

        grp = folium.FeatureGroup(
            name=f"Tournee {t['id_tournee']} (chauffeur {t['id_chauffeur']})",
            show=True,
        )
        folium.PolyLine(
            locations=points,
            color=couleur,
            weight=3,
            opacity=0.8,
            tooltip=f"Tournee {t['id_tournee']} - {len(t['arrets'])} arrets",
        ).add_to(grp)
        grp.add_to(m)

    # --- Controle des couches (activer/desactiver groupes) -----------------
    folium.LayerControl(collapsed=False).add_to(m)

    # --- Legende statuts (bas gauche) --------------------------------------
    legende = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: white; padding: 10px 14px; border: 1px solid #999;
                border-radius: 6px; font-family: sans-serif; font-size: 13px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.3);">
      <b>Run {data['id_run']}</b><br>
      <span style="color:{COULEUR_STATUT['servie']};">&#9679;</span> Servie<br>
      <span style="color:{COULEUR_STATUT['abandonnee']};">&#9679;</span> Non livree<br>
      <span style="color:{COULEUR_STATUT['hors_vague']};">&#9679;</span> Autre<br>
      <span style="color:black;">&#9632;</span> Depot
    </div>
    """
    m.get_root().html.add_child(folium.Element(legende))

    # --- Legende zones (bas droite ; sert le calque "Zones geographiques") -
    lignes_zones = "".join(
        f'<div><span style="color:{PALETTE_ZONES[z]};">&#9679;</span> '
        f'Zone {z} — {NOM_ZONE[z]}</div>'
        for z in sorted(PALETTE_ZONES)
    )
    legende_zones = f"""
    <div style="position: fixed; bottom: 30px; right: 30px; z-index: 1000;
                background: white; padding: 8px 12px; border: 1px solid #999;
                border-radius: 6px; font-family: sans-serif; font-size: 12px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.3);">
      <b>Zones (calque)</b>
      {lignes_zones}
    </div>
    """
    m.get_root().html.add_child(folium.Element(legende_zones))

    return m.get_root().render()
