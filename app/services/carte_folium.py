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
    "abandonnee": "Abandonnee (dans la vague, non livree)",
    "hors_vague": "Hors vague",
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


def rendre_carte_html(data: dict) -> str:
    """Produit une page HTML Folium autonome a partir de la structure
    assemblee par app.crud.carte.assembler_carte().

    Socle Option A : cette fonction rend du HTML pret a embarquer. La meme
    structure 'data' servira de JSON a Leaflet en Option B, sans y toucher.
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
        "abandonnee": folium.FeatureGroup(name="Destinations abandonnees", show=True),
        "hors_vague": folium.FeatureGroup(name="Destinations hors vague", show=False),
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
        ).add_to(groupes_dest[statut])
    for g in groupes_dest.values():
        g.add_to(m)

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

    # --- Legende fixe en surimpression -------------------------------------
    legende = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: white; padding: 10px 14px; border: 1px solid #999;
                border-radius: 6px; font-family: sans-serif; font-size: 13px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.3);">
      <b>Run {data['id_run']}</b><br>
      <span style="color:{COULEUR_STATUT['servie']};">&#9679;</span> Servie<br>
      <span style="color:{COULEUR_STATUT['abandonnee']};">&#9679;</span> Abandonnee<br>
      <span style="color:{COULEUR_STATUT['hors_vague']};">&#9679;</span> Hors vague<br>
      <span style="color:black;">&#9632;</span> Depot
    </div>
    """
    m.get_root().html.add_child(folium.Element(legende))

    return m.get_root().render()
