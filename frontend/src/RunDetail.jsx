import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function RunDetail() {
  const { idRun } = useParams(); // chaine issue de l'URL
  const [data, setData] = useState(null); // null = chargement
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    setData(null);
    setErreur(null);
    fetch(`${API_URL}/runs/${idRun}`)
      .then((r) => {
        if (r.status === 404) throw new Error(`Run ${idRun} introuvable`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json) => setData(json))
      .catch((e) => setErreur(e.message));
  }, [idRun]);

  return (
    <div style={pageStyle}>
      <div style={barreStyle}>
        <Link to="/" style={lienRetourStyle}>← Carte</Link>
        <span style={titreStyle}>Détail du run {idRun}</span>
      </div>

      <div style={corpsStyle}>
        {erreur && <p style={{ color: "#c62828" }}>Erreur : {erreur}</p>}
        {!erreur && data === null && <p>Chargement…</p>}
        {!erreur && data !== null && <RunContenu data={data} />}
      </div>
    </div>
  );
}

// --- Contenu d'un run charge ---
function RunContenu({ data }) {
  const tournees = data.tournees ?? [];
  return (
    <>
      {/* Bandeau resume au niveau run */}
      <div style={resumeStyle}>
        <span><strong>{data.nb_tournees}</strong> tournées</span>
        <span><strong>{data.nb_lots_servis}</strong> lots servis</span>
        <span><strong>{data.distance_totale_km}</strong> km au total</span>
      </div>

      {tournees.map((t) => (
        <TourneeCarte key={t.id_tournee} t={t} />
      ))}
    </>
  );
}

// --- Une tournee : en-tete + tableau des arrets ---
function TourneeCarte({ t }) {
  // Tri defensif par ordre de visite (l'API le garantit deja)
  const arrets = [...(t.affectations ?? [])].sort(
    (a, b) => (a.ordre_visite ?? 0) - (b.ordre_visite ?? 0)
  );

  return (
    <div style={carteStyle}>
      <div style={enteteTourneeStyle}>
        <span style={{ fontWeight: "bold" }}>Tournée {t.id_tournee}</span>
        <span>Véhicule {t.id_vehicule}</span>
        <span>Chauffeur {t.id_chauffeur}</span>
        <span>Dépôt {t.id_station_depart} → {t.id_station_retour}</span>
        <span>{t.distance_totale} km</span>
        <span style={badgeStyle}>{t.statut}</span>
      </div>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Ordre</th>
            <th style={thStyle}>Lot</th>
            <th style={thStyle}>Destination</th>
            <th style={thStyle}>Quantité (m³)</th>
          </tr>
        </thead>
        <tbody>
          {arrets.map((a, i) => (
            <tr key={i}>
              <td style={tdStyle}>{a.ordre_visite}</td>
              <td style={tdStyle}>{a.id_lot}</td>
              <td style={tdStyle}>{formaterDestination(a)}</td>
              <td style={tdStyle}>{a.quantite}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Affichage lisible d'une destination : "Nom (id)", avec replis prudents
function formaterDestination(a) {
  if (a.nom_destination && a.id_destination != null)
    return `${a.nom_destination} (${a.id_destination})`;
  if (a.nom_destination) return a.nom_destination;
  if (a.id_destination != null) return String(a.id_destination);
  return "—";
}

// --- Styles ---
const pageStyle = {
  display: "flex",
  flexDirection: "column",
  minHeight: "100vh",
  width: "100%",
  fontFamily: "sans-serif",
};

const barreStyle = {
  display: "flex",
  alignItems: "center",
  gap: 16,
  padding: "10px 16px",
  borderBottom: "1px solid #ddd",
  background: "#fafafa",
  fontSize: 14,
  flexShrink: 0,
};

const titreStyle = { fontWeight: "bold", fontSize: 16 };

const lienRetourStyle = {
  textDecoration: "none",
  color: "#1565c0",
  fontSize: 14,
};

const corpsStyle = { flex: 1, padding: 16, overflow: "auto" };

const resumeStyle = {
  display: "flex",
  gap: 24,
  padding: "10px 14px",
  marginBottom: 16,
  background: "#eef4fb",
  border: "1px solid #cfe0f3",
  borderRadius: 8,
  fontSize: 14,
};

const carteStyle = {
  border: "1px solid #ddd",
  borderRadius: 8,
  marginBottom: 16,
  overflow: "hidden",
};

const enteteTourneeStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 16,
  alignItems: "center",
  padding: "8px 12px",
  background: "#f5f5f5",
  borderBottom: "1px solid #ddd",
  fontSize: 13,
};

const badgeStyle = {
  background: "#e0e0e0",
  borderRadius: 4,
  padding: "2px 8px",
  fontSize: 12,
};

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
};

const thStyle = {
    textAlign: "left",
    padding: "6px 12px",
    borderBottom: "1px solid #ddd",
    background: "#fafafa",
    fontWeight: "bold",
  };

  const tdStyle = {
    textAlign: "left",
    padding: "6px 12px",
    borderBottom: "1px solid #f0f0f0",
  };