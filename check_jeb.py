import sqlite3
c = sqlite3.connect("livraison.db")
for r in c.execute(
    "SELECT id_destination, nom, latitude, longitude FROM destination "
    "WHERE nom LIKE 'Jebeniana%' ORDER BY id_destination"
):
    print("DB :", r)
