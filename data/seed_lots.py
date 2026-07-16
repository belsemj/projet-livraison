import sqlite3
import random

DB = "livraison.db"
random.seed(42)  # reproductibilite : meme jeu de lots a chaque execution

PRIORITES = ["haute", "moyenne", "basse"]
PRIORITE_WEIGHTS = [0.20, 0.55, 0.25]
CAISSONS = ["standard", "refrigere", "securise"]
CAISSON_WEIGHTS = [0.80, 0.12, 0.08]


def generer_lots():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Securite : ne pas doubler si des lots existent deja
    n = cur.execute("SELECT COUNT(*) FROM lot").fetchone()[0]
    if n > 0:
        print(f"Abandon : la table lot contient deja {n} lignes.")
        conn.close()
        return

    # 1 lot par destination (1..100) + un 2e lot sur 20 destinations = 120 lots
    destinations = list(range(1, 101))
    extra = random.sample(destinations, 20)
    plan = destinations + extra

    lots = []
    for id_dest in plan:
        volume = round(random.uniform(5, 80), 2)
        priorite = random.choices(PRIORITES, PRIORITE_WEIGHTS)[0]
        fragile = 1 if random.random() < 0.15 else 0
        caisson = random.choices(CAISSONS, CAISSON_WEIGHTS)[0]
        lots.append((volume, priorite, fragile, caisson, id_dest))

    cur.executemany(
        "INSERT INTO lot (volume, priorite, fragile, caisson_requis, id_destination) "
        "VALUES (?, ?, ?, ?, ?)",
        lots,
    )
    conn.commit()
    print(f"{len(lots)} lots inseres.")
    conn.close()


if __name__ == "__main__":
    generer_lots()
