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

| Domaine               | Outil                                       |
| --------------------- | ------------------------------------------- |
| API / backend         | FastAPI + Uvicorn                           |
| Base de données       | SQLite (développement) → PostgreSQL (cible) |
| ORM                   | SQLAlchemy                                  |
| Optimisation          | Google OR-Tools                             |
| Données / ML          | pandas, scikit-learn                        |
| Géocodage / distances | geopy, OSRM / OpenRouteService              |
| Cartographie          | Folium / Leaflet                            |

## Feuille de route (8 semaines)

1. **S1** — Cadrage, analyse du besoin, état de l'art, spécification _(terminée)_
2. **S2** — Modélisation des données (SQL/UML), vérification du géocodage
3. **S3–S4** — Développement CRUD (FastAPI + base de données)
4. **S4–S5** — Construction de la matrice des distances (OSRM / OpenRouteService)
5. **S5–S6** — Optimisation MDVRP avec OR-Tools
6. **S6–S7** — Module d'analyse ML (clustering, régression, KPIs)
7. **S7–S8** — Intégration, cartographie, rédaction du rapport final

data/seed.sql est la source de vérité des coordonnées. Les fichiers rapport_geocodage.csv, regeocodage_controle.csv et echantillon_routier.csv sont des traces d'analyse S2/S4 : ils reflètent l'état à leur date de production et ne doivent pas être mis à jour.

D18 | S4 J5 | Endpoint agrégé GET /runs/{id_run} (tournées + affectations
imbriquées) reporté en S6. Le filtrage plat /affectations?id_run= est
implémenté en S4 J5 et suffit à la S5. Forme exacte de l'agrégat à définir
avec les besoins réels de l'écran 4.

D19 | S4 J5 | Retour au depot le plus proche modelise par un noeud d'arrivee
virtuel par vehicule. La matrice passe de 105x105 a (105+V)x(105+V). Le cout
i -> E_v vaut min sur les 5 depots de distance(i, depot_k), lue sur la
matrice routiere asymetrique. Le depot de retour effectif est reconstruit
apres resolution par argmin et ecrit dans tournee.id_station_retour.
Alternative ecartee : retour impose au depot de depart (contredit S2).

D20 | S4 J5 | Fractionnement des lots differe. Le solveur du J1 traite un
CVRP multi-depots classique : un lot = un noeud = un vehicule. Le
pre-decoupage en noeuds jumeaux (Q_min = 25 %) sera introduit au J3
uniquement si les taux de remplissage revelent une tension sur la capacite.
Le fractionnement dynamique (SDVRP, formulation CP-SAT) est ecarte du
perimetre du stage et signale comme perspective dans le rapport.

D21 | S4 J5 | Taille de flotte parametrable (n_vehicules, defaut 10 conforme
au cahier des charges). Q1 restant ouverte (11 mobilisables contre 10
annonces), les deux valeurs seront comparees et l'ecart traite comme un
resultat d'analyse et non comme une hypothese figee.

D22 | S4 J5 | Fonction objectif = distance totale + penalite de non-livraison
(AddDisjunction, cout eleve par lot). Garantit une solution exploitable meme
en capacite insuffisante, et identifie les lots abandonnes. Alternative
ecartee : livraison obligatoire, qui ne renvoie aucune solution en cas
d'infaisabilite.

D23 — Flotte mobilisable par le solveur. Un véhicule entre dans la flotte si assurance = 1 ET id_chauffeur IS NOT NULL ET chauffeur.statut = 'actif'. Le champ vehicule.statut n'est pas discriminant (les 12 sont à actif). Le véhicule 11 reste exclu : non assuré. Flotte retenue : 11 véhicules, capacités standard 114 / réfrigéré 34 / sécurisé 14.
D24 — Réactivation du chauffeur 12. Chauffeur 12 (Tarek F., station 3) repassé de conge à actif et apparié au véhicule 12 (réfrigéré, capacité 18, station 3). Motif : la capacité réfrigérée mobilisable (16) était inférieure au volume des lots réfrigérés (16,2), rendant le problème infaisable. Modification du jeu de test, non du modèle — à confirmer par M. Zghili, qui peut préférer assumer le déficit.
D25 — Doublon Jebeniana. Le remplacement de Kerkennah (S4 J3) a introduit une seconde destination nommée Jebeniana, à ~400 m de l'existante. Renommage en Jebeniana Est (id 71) et Jebeniana Centre (id 72) plutôt que fusion, pour préserver l'indexation canonique et éviter la régénération des matrices. Les deux restent des points de livraison distincts. Note : le plancher D13 (3 km) s'applique à cette paire, dont la distance réelle est de ~0,4 km.
D26 — Mise à l'échelle des volumes. OR-Tools n'accepte que des entiers dans une dimension de capacité. Volumes (0,11 à 1,58) et capacités convertis en centièmes (×100) à l'entrée du solveur, conversion inverse à l'écriture des résultats.
D29 | S5 J2 | Contrainte de caisson implementee par restriction du domaine
de VehicleVar (SetValues), et non par SetAllowedVehiclesForIndex : le typemap
SWIG de cette methode est defaillant en ortools 9.15 (absl::Span<int const>
non converti, quelle que soit la forme de la sequence Python). La valeur -1
est maintenue dans le domaine pour preserver l'effet des disjonctions D28.

D30 | S5 J2 | Surcout de l'hypothese B mesure a budget de temps egal (60 s) :
3 130,0 km sans contrainte contre 4 321,6 km avec, soit +38,1 %, a service
identique (120/120 lots livres). La contrainte est rendue debrayable
(parametre caissons) pour que la mesure reste reproductible.

D31 | S5 J4 | Deux identifiants distincts : id_vague sur lot (ensemble de
commandes a traiter, fige avant calcul) et id_run sur tournee (identifiant
d'une execution du solveur). Une vague peut donner lieu a plusieurs runs.
Alternative ecartee : id_run unique sur les deux tables, qui aurait confondu
l'entree et la sortie du solveur.

D32 | S5 J4 | Reorganisation de la flotte : un vehicule standard et un
refrigere par depot (10), plus un unique vehicule securise. Le securise est
place au depot 1, contraint par la capacite : le depot 1 concentre 40,13 m3
et deux vehicules plafonnent a 40,00. Les lots securises sont consolides au
depot 1 par regle de donnees, faute de quoi le solveur devrait modeliser des
noeuds de ramassage. Modification de donnees de reference, de meme nature que
D15 : artefact de jeu de test, a valider par M. Zghili.

D33 l'endpoint détail GET /runs/{id_run} remonte désormais id_destination et nom_destination au niveau arrêt (jointure Lot → Destination dans crud/run.py). L'écran détail affiche « Nom (id) ». La version « ids seulement » de D32 est levée pour cet endpoint.

D35 — Fractionnement clos : canal unifié « lot non servi » à raison typée.

Décision. Un lot non livré remonte désormais par un seul canal, avec une
raison typée dérivée de l'état solveur post-solve (source unique de vérité,
non un pré-diagnostic) : abandon_solveur (aucun véhicule compatible :
caisson/source) ou capacite_locale (véhicules compatibles, capacité
insuffisante).

Conséquences.

- controler() : toute insuffisance de capacité (locale par dépôt×caisson ET
  globale flotte) passe en [info] non bloquant. Plus aucun 409 sur une
  question de volume ; le solveur lâche le surplus par disjonction. Restent
  bloquantes les seules erreurs de données/modèle (matrice, géométrie,
  station source manquante).
- solveur : \_restreindre_vehicules scindé ; le domaine autorisé par lot,
  jusque-là jeté, est capturé et sert à classer chaque non-servi.
- Persistance : nouvelle table lot_non_servi (id_run, id_lot, raison),
  écrite dans la transaction du run. id_run entier sans FK (cohérent avec
  tournee). Migration d4f7a2c9e1b6.
- Lecture : GET /runs/{id} et la carte lisent ce fait persisté ; fin de la
  divergence J2 (map vs résumé). Priorité couleur révisée : rouge > vert >
  gris (une destination avec au moins un lot abandonné est rouge, l'abandon
  n'est jamais masqué par un lot servi voisin).

Dette. Clé de statut carto « hors_vague » conservée pour compat front alors
que sa sémantique est devenue « autre destination » ; renommage différé.
