from app.database import SessionLocal
from app.services.distances import (
    charger_noeuds, construire_matrice, controler, sauvegarder,
    matrice_pour_solveur, entite_vers_index, index_vers_entite,
)

db = SessionLocal()
noeuds = charger_noeuds(db)
print(f"Noeuds charges : {len(noeuds)}")
print(f"  index 0   -> {noeuds[0].type} {noeuds[0].id_entite} : {noeuds[0].nom}")
print(f"  index 4   -> {noeuds[4].type} {noeuds[4].id_entite} : {noeuds[4].nom}")
print(f"  index 5   -> {noeuds[5].type} {noeuds[5].id_entite} : {noeuds[5].nom}")
print(f"  index 104 -> {noeuds[104].type} {noeuds[104].id_entite} : {noeuds[104].nom}")

matrice = construire_matrice(noeuds)
print(f"\nMatrice brute : {matrice.shape}")

anomalies = controler(matrice, noeuds)
print(f"\nControles matrice brute : {len(anomalies)} anomalie(s)")
for a in anomalies:
    print("  -", a)

# --- D13 : plancher applique uniquement en sortie, pas au stockage ---
ajustee = matrice_pour_solveur(matrice)
print(f"\nControles matrice solveur : {len(controler(ajustee, noeuds))} anomalie(s)")
print(f"  Depot Bizerte -> Bizerte Ville : brut {matrice[1, 37]:.1f} km, "
      f"ajuste {ajustee[1, 37]:.1f} km")
print(f"  Depot El Ghazala -> La Marsa   : brut {matrice[0, 5]:.1f} km, "
      f"ajuste {ajustee[0, 5]:.1f} km")

print("\nCorrespondance index :")
print("  entite_vers_index('station', 4)     =", entite_vers_index("station", 4))
print("  entite_vers_index('destination', 1) =", entite_vers_index("destination", 1))
print("  index_vers_entite(3)                =", index_vers_entite(3))
print("  index_vers_entite(5)                =", index_vers_entite(5))

print("\nControles de vraisemblance (km, vol d'oiseau) :")
paires = [(0, 3, "El Ghazala - Sfax", 235), (0, 1, "El Ghazala - Bizerte", 55),
          (0, 2, "El Ghazala - Sousse", 120), (3, 4, "Sfax - Gabes", 115)]
for i, j, libelle, attendu in paires:
    print(f"  {libelle:<25} {matrice[i, j]:>8.1f}   (ordre attendu ~{attendu})")

print(f"\nDistance max : {matrice.max():.1f} km")

sauvegarder(matrice, noeuds)          # matrice BRUTE : c'est le coeur de D13
print("\nFichiers ecrits dans data/")
db.close()
