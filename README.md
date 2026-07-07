# Application web d'affectation des tâches de livraison

Projet de stage — **Progress Engineering** (Parc Technologique El Ghazala, Ariana).
Conception et développement d'une application web d'affectation des tâches de livraison,
dotée d'un module d'intelligence artificielle pour l'optimisation des tournées et
l'analyse de performance.

- **Stagiaire :** Belsem
- **Encadrant :** M. Mabrouk Zghili — Directeur Technique
- **Problème traité :** tournées de véhicules multi-dépôts avec capacité (MDVRP)
- **Contexte :** 5 dépôts sources, 100 destinations réparties sur les 24 gouvernorats,
  flotte de 10 véhicules actifs.

## Structure du projet

```
projet-livraison/
├── app/          # code de l'application (API, solveur, module ML)
├── data/         # jeux de données (stations.csv, seed.sql)
├── docs/         # notes d'analyse et bilans de semaine
├── notebooks/    # analyses ML exploratoires
├── requirements.txt
├── .gitignore
└── README.md
```

## Installation

Créer et activer un environnement virtuel, puis installer les dépendances :

```bash
# Créer l'environnement
python -m venv venv

# Activer  (Linux / macOS)
source venv/bin/activate
# Activer  (Windows PowerShell)
venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r requirements.txt
```

## Lancer l'API (vérification de l'environnement)

```bash
uvicorn app.main:app --reload
```

Puis ouvrir http://127.0.0.1:8000 — la réponse confirme que l'environnement fonctionne.
La documentation interactive est disponible sur http://127.0.0.1:8000/docs.

## Stack technique

| Domaine | Outil |
|---|---|
| API / backend | FastAPI + Uvicorn |
| Base de données | SQLite (développement) → PostgreSQL (cible) |
| ORM | SQLAlchemy |
| Optimisation | Google OR-Tools |
| Données / ML | pandas, scikit-learn |
| Géocodage / distances | geopy, OSRM / OpenRouteService |
| Cartographie | Folium / Leaflet |

## Feuille de route (8 semaines)

1. **S1** — Cadrage, analyse du besoin, état de l'art, spécification *(terminée)*
2. **S2** — Modélisation des données (SQL/UML), vérification du géocodage
3. **S3–S4** — Développement CRUD (FastAPI + base de données)
4. **S4–S5** — Construction de la matrice des distances (OSRM / OpenRouteService)
5. **S5–S6** — Optimisation MDVRP avec OR-Tools
6. **S6–S7** — Module d'analyse ML (clustering, régression, KPIs)
7. **S7–S8** — Intégration, cartographie, rédaction du rapport final
