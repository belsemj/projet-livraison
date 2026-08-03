import { useEffect, useMemo, useState, Fragment } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  CircleMarker,
  Polyline,
  Tooltip,
  Popup,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
// Ajoute L.polylineDecorator + L.Symbol.arrowHead (fleches directionnelles)
import "leaflet-polylinedecorator";

// --- Piege 2 : reparer l'icone de marqueur par defaut cassee par Vite ---
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
});

// Centre + zoom pays entier (valeurs de repli avant l'auto-cadrage)
const CENTRE_TUNISIE = [34.5, 9.5];
const ZOOM_INITIAL = 7;

// URL de l'API : variable d'env Vite, avec repli sur le localhost de dev
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Couleurs des destinations (D33-carto) — memes codes que le back
const COULEUR_STATUT = {
  servie: "#2e7d32", // vert
  abandonnee: "#c62828", // rouge
  hors_vague: "#9e9e9e", // gris
};

// Libelles lisibles pour les popups (clef 'hors_vague' conservee cote back,
// mais sa semantique est desormais "autre destination", pas "hors vague").
const LIBELLE_STATUT = {
  servie: "Servie",
  abandonnee: "Non livrée",
  hors_vague: "Autre destination",
};

// Libelles lisibles des raisons d'abandon (miroir des valeurs solveur/API)
const LIBELLE_RAISON = {
  abandon_solveur: "aucun véhicule compatible",
  capacite_locale: "capacité locale insuffisante",
  echec_solveur: "échec du solveur",
};

// Palette 9 tournees (memes couleurs que carte_folium.py)
const PALETTE_TOURNEES = [
  "#1f77b4", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2",
  "#17becf", "#bcbd22", "#008080", "#ff1493",
];

// Palette 7 zones geographiques (D-serie zonage) — memes codes que
// carte_folium.py. Numerotation nord->sud (cf. clustering.py). Distincte du
// vert/rouge/gris des statuts.
const PALETTE_ZONES = {
  1: "#6a51a3", // Grand Tunis  - violet
  2: "#2171b5", // Nord-Ouest   - bleu
  3: "#238b8b", // Sahel        - teal
  4: "#d9a300", // Centre       - or
  5: "#cc6600", // Sfax         - orange brule
  6: "#c51b7d", // Djerid       - magenta
  7: "#8c510a", // Sud-Est      - brun
};
const NOM_ZONE = {
  1: "Grand Tunis", 2: "Nord-Ouest", 3: "Sahel", 4: "Centre",
  5: "Sfax", 6: "Djerid", 7: "Sud-Est",
};

// --- Gestion du redimensionnement ---
// Quand le conteneur de la carte change de taille (passage plein ecran,
// redimensionnement fenetre), Leaflet doit etre prevenu sinon des tuiles
// restent grises. Un ResizeObserver couvre toutes les variations de taille.
function GestionTaille() {
  const map = useMap();
  useEffect(() => {
    const conteneur = map.getContainer();
    const observateur = new ResizeObserver(() => {
      map.invalidateSize();
    });
    observateur.observe(conteneur);
    return () => observateur.disconnect();
  }, [map]);
  return null;
}

// --- Auto-cadrage : ajuste la vue a l'emprise du run au chargement ---
// Enfant du MapContainer (useMap). Se declenche a chaque nouveau run (data),
// pas sur les toggles de couches. fitBounds sur depots + destinations.
function AjusteurVue({ data }) {
  const map = useMap();
  useEffect(() => {
    if (!data) return;
    const points = [
      ...data.depots.map((d) => [d.lat, d.lon]),
      ...data.destinations.map((d) => [d.lat, d.lon]),
    ];
    if (points.length === 0) return;
    const bounds = L.latLngBounds(points);
    // maxZoom : evite un zoom excessif si le run tient sur un seul point
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
  }, [map, data]);
  return null;
}

// --- Fleches directionnelles le long d'une tournee ---
// Composant enfant du MapContainer : ajoute/retire un decorateur imperatif.
// Monte/demonte avec la tournee (rendu conditionnel), donc les fleches
// apparaissent et disparaissent avec la polyligne.
function DecorateurFleches({ tournee, couleur }) {
  const map = useMap();
  // Positions memoisees sur la reference de la tournee : stables tant que le
  // run ne change pas, donc le decorateur n'est pas reconstruit a chaque
  // bascule de case sans rapport.
  const positions = useMemo(
    () => [
      [tournee.depot_depart.lat, tournee.depot_depart.lon],
      ...tournee.arrets.map((a) => [a.lat, a.lon]),
      [tournee.depot_retour.lat, tournee.depot_retour.lon],
    ],
    [tournee]
  );

  useEffect(() => {
    const decorateur = L.polylineDecorator(positions, {
      patterns: [
        {
          offset: "4%",
          repeat: "8%",
          symbol: L.Symbol.arrowHead({
            pixelSize: 10,
            polygon: false, // "V" ouvert plutot qu'un triangle plein
            pathOptions: { stroke: true, weight: 3, color: couleur },
          }),
        },
      ],
    }).addTo(map);

    return () => {
      map.removeLayer(decorateur);
    };
  }, [map, positions, couleur]);

  return null;
}

export default function Carte({ idRun }) {
  const [data, setData] = useState(null);
  const [erreur, setErreur] = useState(null);

  // --- Etat de visibilite des couches (panneau maison, pilote par le state) ---
  const [depotsVisibles, setDepotsVisibles] = useState(true);
  const [statutsVisibles, setStatutsVisibles] = useState({
    servie: true,
    abandonnee: true,
    hors_vague: false, // decoche par defaut : c'est le gris qui encombre
  });
  // Calque zones (ML) : decoche par defaut. C'est une lecture geographique,
  // independante du run et des statuts. Peut cohabiter avec les statuts.
  const [zonesVisibles, setZonesVisibles] = useState(false);
  // { id_tournee: bool }. Une tournee absente de l'objet = visible par defaut.
  const [tourneesVisibles, setTourneesVisibles] = useState({});
  const [tourneesDeployees, setTourneesDeployees] = useState(true);

  useEffect(() => {
    setData(null);
    setErreur(null);
    setTourneesVisibles({}); // reset : toutes visibles par defaut pour le nouveau run
    fetch(`${API_URL}/runs/${idRun}/carte-json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setErreur(e.message));
  }, [idRun]);

  if (erreur) return <p>Erreur de chargement : {erreur}</p>;
  if (!data) return <p>Chargement de la carte…</p>;

  // Une tournee non encore touchee est consideree visible (defaut = coche)
  const tourneeEstVisible = (id) => tourneesVisibles[id] ?? true;

  // --- Etat derive de la case parente "Tournees" ---
  const idsTournees = data.tournees.map((t) => t.id_tournee);
  const valeurs = idsTournees.map(tourneeEstVisible);
  const toutesTournees = valeurs.length > 0 && valeurs.every(Boolean);
  const aucuneTournee = valeurs.every((v) => !v);
  const tourneesPartiel = !toutesTournees && !aucuneTournee;

  const basculerToutesTournees = () => {
    const cible = !toutesTournees; // tout coche -> tout decocher ; sinon tout cocher
    const suivant = {};
    idsTournees.forEach((id) => {
      suivant[id] = cible;
    });
    setTourneesVisibles(suivant);
  };

  const basculerUneTournee = (id) => {
    setTourneesVisibles((prec) => ({ ...prec, [id]: !(prec[id] ?? true) }));
  };

  const basculerStatut = (statut) => {
    setStatutsVisibles((prec) => ({ ...prec, [statut]: !prec[statut] }));
  };

  // Zones effectivement presentes dans les donnees (pour la legende dynamique)
  const zonesPresentes = [
    ...new Set(
      data.destinations
        .map((d) => d.id_zone)
        .filter((z) => z != null)
    ),
  ].sort((a, b) => a - b);

  return (
    <div style={{ position: "relative", height: "100%", width: "100%" }}>
      <MapContainer
        center={CENTRE_TUNISIE}
        zoom={ZOOM_INITIAL}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Prevenir Leaflet des changements de taille du conteneur */}
        <GestionTaille />

        {/* Auto-cadrage sur l'emprise du run */}
        <AjusteurVue data={data} />

        {/* Depots : marqueurs par defaut */}
        {depotsVisibles &&
          data.depots.map((d, i) => (
            <Marker key={`depot-${i}`} position={[d.lat, d.lon]}>
              <Tooltip>Depot : {d.nom}</Tooltip>
              <Popup>
                <b>Dépôt</b>
                <br />
                {d.nom}
              </Popup>
            </Marker>
          ))}

        {/* Destinations : cercles colores, filtres par statut visible */}
        {data.destinations
          .filter((dest) => statutsVisibles[dest.statut])
          .map((dest, i) => {
            const nonServis = dest.lots_non_servis ?? [];
            return (
              <CircleMarker
                key={`dest-${dest.nom}-${i}`}
                center={[dest.lat, dest.lon]}
                radius={5}
                pathOptions={{
                  color: COULEUR_STATUT[dest.statut],
                  fillColor: COULEUR_STATUT[dest.statut],
                  fillOpacity: 0.9,
                }}
              >
                <Tooltip>
                  {dest.nom} ({dest.gouvernorat})
                </Tooltip>
                <Popup>
                  <b>{dest.nom}</b>
                  <br />
                  Gouvernorat : {dest.gouvernorat}
                  <br />
                  Statut : {LIBELLE_STATUT[dest.statut] ?? dest.statut}
                  {nonServis.length > 0 && (
                    <>
                      <br />
                      <b>Lot(s) non livré(s) :</b>
                      <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                        {nonServis.map((l) => (
                          <li key={l.id_lot}>
                            Lot {l.id_lot} :{" "}
                            {LIBELLE_RAISON[l.raison] ?? l.raison}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </Popup>
              </CircleMarker>
            );
          })}

        {/* Zones ML : calque analytique SEPARE (D-serie zonage).
            Memes destinations, colorees par zone au lieu du statut. Cohabite
            avec les statuts (deux cercles superposables) ; on peut decocher
            les statuts pour ne voir que les zones. */}
        {zonesVisibles &&
          data.destinations.map((dest, i) => {
            if (dest.id_zone == null) return null;
            const couleur = PALETTE_ZONES[dest.id_zone] ?? "#000000";
            return (
              <CircleMarker
                key={`zone-${dest.id_destination ?? dest.nom}-${i}`}
                center={[dest.lat, dest.lon]}
                radius={6}
                pathOptions={{
                  color: couleur,
                  fillColor: couleur,
                  fillOpacity: 0.85,
                }}
              >
                <Tooltip>
                  {dest.nom} — Zone {dest.id_zone} (
                  {NOM_ZONE[dest.id_zone] ?? "?"})
                </Tooltip>
              </CircleMarker>
            );
          })}

        {/* Tournees : polyligne + fleches de sens, filtrees par visibilite */}
        {data.tournees.map((t, i) => {
          if (!tourneeEstVisible(t.id_tournee)) return null;
          const couleur = PALETTE_TOURNEES[i % PALETTE_TOURNEES.length];
          const points = [
            [t.depot_depart.lat, t.depot_depart.lon],
            ...t.arrets.map((a) => [a.lat, a.lon]),
            [t.depot_retour.lat, t.depot_retour.lon],
          ];
          // Le champ chauffeur existe cote back (cf. libelles Folium) ;
          // on le lit defensivement pour ne pas casser si le nom differe.
          const chauffeur = t.id_chauffeur ?? t.chauffeur;
          return (
            <Fragment key={`tournee-${t.id_tournee}`}>
              <Polyline
                positions={points}
                pathOptions={{ color: couleur, weight: 3, opacity: 0.8 }}
              >
                <Tooltip>
                  Tournee {t.id_tournee} — {t.arrets.length} arrets
                </Tooltip>
                <Popup>
                  <b>Tournée {t.id_tournee}</b>
                  <br />
                  {chauffeur != null && (
                    <>
                      Chauffeur : {chauffeur}
                      <br />
                    </>
                  )}
                  Arrêts : {t.arrets.length}
                </Popup>
              </Polyline>
              <DecorateurFleches tournee={t} couleur={couleur} />
            </Fragment>
          );
        })}
      </MapContainer>

      {/* --- Panneau de controle des couches (remplace LayersControl) --- */}
      <div style={panneauStyle}>
        <div style={{ fontWeight: "bold", marginBottom: 6 }}>Couches</div>

        <label style={ligneStyle}>
          <input
            type="checkbox"
            checked={depotsVisibles}
            onChange={() => setDepotsVisibles((v) => !v)}
          />
          <span>Dépôts ({data.depots.length})</span>
        </label>

        <label style={ligneStyle}>
          <input
            type="checkbox"
            checked={statutsVisibles.servie}
            onChange={() => basculerStatut("servie")}
          />
          <span style={{ color: COULEUR_STATUT.servie }}>● Servies</span>
        </label>

        <label style={ligneStyle}>
          <input
            type="checkbox"
            checked={statutsVisibles.abandonnee}
            onChange={() => basculerStatut("abandonnee")}
          />
          <span style={{ color: COULEUR_STATUT.abandonnee }}>● Non livrées</span>
        </label>

        <label style={ligneStyle}>
          <input
            type="checkbox"
            checked={statutsVisibles.hors_vague}
            onChange={() => basculerStatut("hors_vague")}
          />
          <span style={{ color: COULEUR_STATUT.hors_vague }}>● Autres</span>
        </label>

        {/* Calque zones ML : independant des statuts */}
        <div style={{ marginTop: 6, borderTop: "1px solid #eee", paddingTop: 6 }}>
          <label style={ligneStyle}>
            <input
              type="checkbox"
              checked={zonesVisibles}
              onChange={() => setZonesVisibles((v) => !v)}
            />
            <span>Zones géographiques ({zonesPresentes.length})</span>
          </label>
        </div>

        {/* Groupe Tournees : case parente + sous-cases (une par tournee) */}
        <div style={{ marginTop: 6, borderTop: "1px solid #eee", paddingTop: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <button
              type="button"
              onClick={() => setTourneesDeployees((v) => !v)}
              style={boutonDeplierStyle}
              title={tourneesDeployees ? "Replier" : "Déplier"}
            >
              {tourneesDeployees ? "▾" : "▸"}
            </button>
            <label
              style={{ ...ligneStyle, marginBottom: 0, fontWeight: "bold" }}
            >
              <input
                type="checkbox"
                ref={(el) => {
                  // etat "partiel" (ni tout coche ni tout decoche)
                  if (el) el.indeterminate = tourneesPartiel;
                }}
                checked={toutesTournees}
                onChange={basculerToutesTournees}
              />
              <span>Tournées ({idsTournees.length})</span>
            </label>
          </div>

          {tourneesDeployees && (
            <div style={{ paddingLeft: 18, marginTop: 4 }}>
              {data.tournees.map((t, i) => {
                const couleur = PALETTE_TOURNEES[i % PALETTE_TOURNEES.length];
                return (
                  <label
                    key={`ctrl-tournee-${t.id_tournee}`}
                    style={ligneStyle}
                  >
                    <input
                      type="checkbox"
                      checked={tourneeEstVisible(t.id_tournee)}
                      onChange={() => basculerUneTournee(t.id_tournee)}
                    />
                    <span
                      style={{
                        display: "inline-block",
                        width: 10,
                        height: 10,
                        borderRadius: 2,
                        background: couleur,
                        flexShrink: 0,
                      }}
                    />
                    <span>Tournée {t.id_tournee}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* --- Legende zones : visible seulement quand le calque zones est actif --- */}
      {zonesVisibles && zonesPresentes.length > 0 && (
        <div style={legendeZonesStyle}>
          <div style={{ fontWeight: "bold", marginBottom: 4 }}>
            Zones (calque)
          </div>
          {zonesPresentes.map((z) => (
            <div key={`leg-zone-${z}`} style={ligneLegendeStyle}>
              <span style={{ color: PALETTE_ZONES[z] ?? "#000" }}>●</span>
              <span>
                Zone {z} — {NOM_ZONE[z] ?? "?"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Styles du panneau (inline, coherents avec l'ancienne legende Folium) ---
const panneauStyle = {
  position: "absolute",
  top: 12,
  right: 12,
  zIndex: 1000, // au-dessus des panes et controles Leaflet
  background: "white",
  padding: "10px 12px",
  border: "1px solid #999",
  borderRadius: 6,
  fontFamily: "sans-serif",
  fontSize: 13,
  boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
  maxHeight: "85%",
  overflowY: "auto",
};

const ligneStyle = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  marginBottom: 4,
  cursor: "pointer",
};

const boutonDeplierStyle = {
  border: "none",
  background: "none",
  cursor: "pointer",
  fontSize: 12,
  padding: 0,
  width: 14,
  lineHeight: 1,
};

// Legende du calque zones (bas GAUCHE, au-dessus du bouton plein ecran de
// CarteView pour ne pas le recouvrir ; le panneau Couches occupe le bas droite
// quand il est deploye, d'ou le choix du cote gauche).
const legendeZonesStyle = {
    position: "absolute",
    bottom: 56,
    left: 12,
    zIndex: 1000,
    background: "white",
    padding: "8px 12px",
    border: "1px solid #999",
    borderRadius: 6,
    fontFamily: "sans-serif",
    fontSize: 12,
    boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
  };
const ligneLegendeStyle = {
  display: "flex",
  alignItems: "center",
  gap: 6,
};