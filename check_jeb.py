import sqlite3

c = sqlite3.connect("livraison.db")
c.row_factory = sqlite3.Row

print("-- les deux Jebeniana --")
for r in c.execute(
    "SELECT d.id_destination, d.nom, d.latitude, d.longitude, "
    "(SELECT COUNT(1) FROM lot l WHERE l.id_destination = d.id_destination) AS nb_lots "
    "FROM destination d WHERE d.nom = 'Jebeniana' ORDER BY d.id_destination"
):
    print(f"  id={r['id_destination']:3d}  ({r['latitude']}, {r['longitude']})  "
          f"{r['nb_lots']} lot(s)")

print("\n-- autres doublons de nom eventuels --")
lignes = list(c.execute(
    "SELECT nom, COUNT(1) AS nb FROM destination "
    "GROUP BY nom HAVING nb > 1 ORDER BY nb DESC"
))
if lignes:
    for r in lignes:
        print(f"  {r['nom']} : {r['nb']} occurrences")
else:
    print("  aucun")

print("\n-- destinations sans aucun lot --")
n = c.execute(
    "SELECT COUNT(1) FROM destination d WHERE NOT EXISTS "
    "(SELECT 1 FROM lot l WHERE l.id_destination = d.id_destination)"
).fetchone()[0]
print(f"  {n} destination(s) non desservie(s)")
