import sqlite3
c = sqlite3.connect("livraison.db")
print("chauffeur 12 :", c.execute(
    "SELECT id_chauffeur, nom, statut, id_station FROM chauffeur WHERE id_chauffeur=12"
).fetchone())
print("vehicule 12  :", c.execute(
    "SELECT id_vehicule, capacite, assurance, statut, type_caisson, id_station, id_chauffeur "
    "FROM vehicule WHERE id_vehicule=12"
).fetchone())
