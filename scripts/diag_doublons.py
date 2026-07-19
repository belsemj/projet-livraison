import sqlite3

conn = sqlite3.connect("livraison.db")
cur = conn.cursor()

paires = [(2, 33), (3, 48), (4, 65), (5, 84)]

for id_st, id_dest in paires:
    cur.execute("SELECT nom, latitude, longitude FROM station WHERE id_station=?", (id_st,))
    st = cur.fetchone()
    cur.execute(
        "SELECT nom, gouvernorat, latitude, longitude FROM destination WHERE id_destination=?",
        (id_dest,),
    )
    de = cur.fetchone()
    print(f"--- station {id_st} / destination {id_dest}")
    print(f"    STATION     : {st[0]:35s} {st[1]}, {st[2]}")
    print(f"    DESTINATION : {de[0]:35s} ({de[1]}) {de[2]}, {de[3]}")

conn.close()
