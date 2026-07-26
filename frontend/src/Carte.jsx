import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, CircleMarker, Polyline, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

// --- Piege 2 : reparer l'icone de marqueur par defaut cassee par Vite ---
// Leaflet reference ses images d'icones par des chemins qui ne survivent
// pas au bundling. On les reimporte explicitement et on reconfigure.
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
});

// Centre + zoom pays entier (memes valeurs que la carte Folium)
const CENTRE_TUNISIE = [34.5, 9.5];
const ZOOM_INITIAL = 7;

// Couleurs des destinations (D33-carto) — memes codes que le back
const COULEUR_STATUT = {
  servie: "#2e7d32",       // vert
  abandonnee: "#c62828",   // rouge
  hors_vague: "#9e9e9e",   // gris
};

// Palette 9 tournees (memes couleurs que carte_folium.py)
const PALETTE_TOURNEES = [
  "#1f77b4", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2",
  "#17becf", "#bcbd22", "#008080", "#ff1493",
];

export default function Carte({ idRun }) {
  const [data, setData] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    fetch(`http://localhost:8000/runs/${idRun}/carte-json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setErreur(e.message));
  }, [idRun]);

  if (erreur) return <p>Erreur de chargement : {erreur}</p>;
  if (!data) return <p>Chargement de la carte…</p>;

  return (
    <MapContainer
      center={CENTRE_TUNISIE}
      zoom={ZOOM_INITIAL}
      style={{ height: "100vh", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Depots : marqueurs par defaut */}
      {data.depots.map((d, i) => (
        <Marker key={`depot-${i}`} position={[d.lat, d.lon]}>
          <Tooltip>Depot : {d.nom}</Tooltip>
        </Marker>
      ))}

      {/* Destinations : cercles colores par statut */}
      {data.destinations.map((dest, i) => (
        <CircleMarker
          key={`dest-${i}`}
          center={[dest.lat, dest.lon]}
          radius={5}
          pathOptions={{
            color: COULEUR_STATUT[dest.statut],
            fillColor: COULEUR_STATUT[dest.statut],
            fillOpacity: 0.9,
          }}
        >
          <Tooltip>{dest.nom} ({dest.gouvernorat})</Tooltip>
        </CircleMarker>
      ))}

      {/* Tournees : polylignes depot -> arrets -> depot */}
      {data.tournees.map((t, i) => {
        const points = [
          [t.depot_depart.lat, t.depot_depart.lon],
          ...t.arrets.map((a) => [a.lat, a.lon]),
          [t.depot_retour.lat, t.depot_retour.lon],
        ];
        return (
          <Polyline
            key={`tournee-${i}`}
            positions={points}
            pathOptions={{
              color: PALETTE_TOURNEES[i % PALETTE_TOURNEES.length],
              weight: 3,
              opacity: 0.8,
            }}
          >
            <Tooltip>Tournee {t.id_tournee} — {t.arrets.length} arrets</Tooltip>
          </Polyline>
        );
      })}
    </MapContainer>
  );
}