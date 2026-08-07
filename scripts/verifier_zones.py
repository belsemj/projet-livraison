"""Verification read-only du zonage calcule DEPUIS LA BASE (pas le CSV).

Confirme que les coords en base produisent bien les 7 zones attendues et que
le mapping est complet. N'ecrit rien. Lancer : python -m scripts.verifier_zones
"""
from app.database import SessionLocal
from app.services.clustering import calculer_zones


def main():
    db = SessionLocal()
    try:
        res = calculer_zones(db)
    finally:
        db.close()

    total = sum(z["n"] for z in res["zones"])
    print(f"k = {res['k']}  |  {total} destinations")
    for z in res["zones"]:
        c = z["centre"]
        print(f"  Zone {z['id_zone']}  n={z['n']:>2}  "
              f"centre {c['lat']}N {c['lon']}E")
    print("tailles :", [z["n"] for z in res["zones"]])

    assert total == 100, f"attendu 100, obtenu {total}"
    assert sorted(res["mapping"]) == list(range(1, 101)), "ids manquants"
    assert set(res["mapping"].values()) == set(range(1, res["k"] + 1))
    print("OK : mapping complet, 1 zone par destination")


if __name__ == "__main__":
    main()
