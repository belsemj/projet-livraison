"""Re-geocodage provisoire des 4 depots confondus avec leur chef-lieu (D13).
Mode diagnostic : n'ecrit rien, affiche seulement les propositions.
"""
import sqlite3
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from time import sleep

RAYON_MAX_KM = 15.0

# id_station -> requetes Nominatim, de la plus precise a la plus large
CIBLES = {
    2: ["Zone Industrielle Bizerte, Tunisie",
        "Menzel Jemil, Bizerte, Tunisie"],
    3: ["Zone Industrielle Sidi Abdelhamid, Sousse, Tunisie",
        "Zone Industrielle Sousse, Tunisie"],
    4: ["Zone Industrielle Sidi Salem, Sfax, Tunisie",
        "Zone Industrielle Poudriere, Sfax, Tunisie"],
    5: ["Zone Industrielle Gabes, Tunisie",
        "Ghannouch, Gabes, Tunisie"],
}

geo = Nominatim(user_agent="projet-livraison-depots")
conn = sqlite3.connect("livraison.db")
cur = conn.cursor()

for id_st, requetes in CIBLES.items():
    cur.execute("SELECT nom, latitude, longitude FROM station WHERE id_station=?", (id_st,))
    nom, lat0, lon0 = cur.fetchone()
    print(f"\n=== {nom} (actuel : {lat0}, {lon0})")

    for req in requetes:
        try:
            r = geo.geocode(req, country_codes="tn", timeout=10)
        except Exception as e:
            print(f"    [erreur] {req} -> {e}")
            sleep(1.5)
            continue

        if r is None:
            print(f"    [echec]  {req}")
            sleep(1.5)
            continue

        d = geodesic((lat0, lon0), (r.latitude, r.longitude)).km
        statut = "OK" if 0.3 < d <= RAYON_MAX_KM else "REJET"
        print(f"    [{statut:5s}] {req}")
        print(f"             -> {round(r.latitude, 4)}, {round(r.longitude, 4)}  "
              f"(ecart {d:.2f} km)")
        print(f"             -> {r.address[:90]}")
        sleep(1.5)

conn.close()
