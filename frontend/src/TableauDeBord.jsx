import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Ecran dedie "Tableau de bord" : lit GET /runs/{id}/kpis (calcul back,
// affichage front). Le run est choisi via un selecteur alimente par GET /runs.
// Au montage, si l'URL porte ?run=<id> (transmis depuis la carte), on demarre
// sur ce run ; sinon, le plus recent.
export default function TableauDeBord() {
  const [searchParams] = useSearchParams();
  const [runs, setRuns] = useState(null); // liste pour le selecteur (null = chargement)
  const [idRun, setIdRun] = useState(null); // run selectionne
  const [kpis, setKpis] = useState(null); // KPIs du run (null = chargement)
  const [erreur, setErreur] = useState(null);

  // 1. Charger la liste des runs (selecteur). Run initial = ?run= si present
  //    et valide, sinon le plus recent. Lu une seule fois au montage.
  useEffect(() => {
    fetch(`${API_URL}/runs`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((liste) => {
        setRuns(liste);
        if (liste.length > 0) {
          const demande = Number(searchParams.get("run"));
          const existe = liste.some((r) => r.id_run === demande);
          setIdRun(existe ? demande : liste[0].id_run); // liste triee desc
        }
      })
      .catch((e) => setErreur(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2. Charger les KPIs du run selectionne.
  useEffect(() => {
    if (idRun == null) return;
    setKpis(null);
    setErreur(null);
    fetch(`${API_URL}/runs/${idRun}/kpis`)
      .then((r) => {
        if (r.status === 404) throw new Error(`Run ${idRun} introuvable`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setKpis)
      .catch((e) => setErreur(e.message));
  }, [idRun]);

  return (
    <div style={pageStyle}>
      <div style={barreStyle}>
        <Link to="/" style={lienRetourStyle}>← Carte</Link>
        <span style={titreStyle}>Tableau de bord</span>
        <div style={{ flex: 1 }} />
        {runs && runs.length > 0 && (
          <label style={{ fontSize: 14 }}>
            Run{" "}
            <select
              value={idRun ?? ""}
              onChange={(e) => setIdRun(Number(e.target.value))}
              style={selectStyle}
            >
              {runs.map((r) => (
                <option key={r.id_run} value={r.id_run}>
                  Run {r.id_run}
                  {r.nb_lots_non_servis > 0
                    ? ` — ${r.nb_lots_non_servis} abandon${r.nb_lots_non_servis > 1 ? "s" : ""}`
                    : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {idRun != null && (
          <Link to={`/runs/${idRun}`} style={lienDetailStyle}>
            Détail du run →
          </Link>
        )}
      </div>

      <div style={corpsStyle}>
        {erreur && <p style={{ color: "#c62828" }}>Erreur : {erreur}</p>}
        {!erreur && runs && runs.length === 0 && (
          <p>Aucun run disponible. Lancez d'abord une optimisation.</p>
        )}
        {!erreur && idRun != null && kpis === null && <p>Chargement…</p>}
        {!erreur && kpis && <KpisContenu kpis={kpis} />}
      </div>
    </div>
  );
}

// --- Contenu KPIs d'un run charge ---
function KpisContenu({ kpis }) {
  const fractionnement =
    kpis.nb_lots_servis !== kpis.nb_lots_distincts_servis;

  return (
    <>
      {/* Chiffres cles */}
      <div style={cartesRangeeStyle}>
        <CarteKpi titre="Distance totale" valeur={`${kpis.distance_totale_km} km`} />
        <CarteKpi titre="Remplissage moyen" valeur={`${kpis.remplissage_moyen_pct} %`} />
        <CarteKpi
          titre="Lots livrés"
          valeur={kpis.nb_lots_distincts_servis}
          sous={fractionnement ? `${kpis.nb_lots_servis} livraisons (fractionnement)` : null}
        />
        <CarteKpi
          titre="Lots non servis"
          valeur={kpis.nb_lots_non_servis}
          accent={kpis.nb_lots_non_servis > 0 ? "#c62828" : "#2e7d32"}
        />
        <CarteKpi
          titre="Destinations servies"
          valeur={kpis.nb_destinations_servies}
          sous={
            kpis.nb_destinations_abandonnees > 0
              ? `${kpis.nb_destinations_abandonnees} abandonnée${kpis.nb_destinations_abandonnees > 1 ? "s" : ""}`
              : "0 abandon"
          }
          accent={kpis.nb_destinations_abandonnees > 0 ? "#c62828" : undefined}
        />
      </div>

      {/* Equilibrage : volume ET distance */}
      <div style={sectionTitreStyle}>Équilibrage de charge entre tournées</div>
      <div style={cartesRangeeStyle}>
        <PanneauEquilibrage titre="Volume" unite="m³" d={kpis.equilibrage_volume} />
        <PanneauEquilibrage titre="Distance" unite="km" d={kpis.equilibrage_distance} />
      </div>

      {/* Detail par tournee */}
      <div style={sectionTitreStyle}>
        Détail par tournée ({kpis.nb_tournees})
      </div>
      <TableTournees
        tournees={kpis.tournees}
        volMin={kpis.equilibrage_volume.min}
        volMax={kpis.equilibrage_volume.max}
        distMin={kpis.equilibrage_distance.min}
        distMax={kpis.equilibrage_distance.max}
      />
    </>
  );
}

// --- Une carte "chiffre cle" ---
function CarteKpi({ titre, valeur, sous, accent }) {
  return (
    <div style={carteKpiStyle}>
      <div style={carteTitreStyle}>{titre}</div>
      <div style={{ ...carteValeurStyle, color: accent ?? "#1565c0" }}>{valeur}</div>
      {sous && <div style={carteSousStyle}>{sous}</div>}
    </div>
  );
}

// --- Panneau d'equilibrage (min / moyenne / max / ecart-type + barre) ---
function PanneauEquilibrage({ titre, unite, d }) {
  const etendue = d.max - d.min;
  // Position du repere "moyenne" sur la barre min..max (50 % si tout egal).
  const posMoy = etendue > 0 ? ((d.moyenne - d.min) / etendue) * 100 : 50;
  return (
    <div style={panneauEqStyle}>
      <div style={carteTitreStyle}>
        {titre} ({unite})
      </div>
      <div style={eqLigneStyle}>
        <span>min <strong>{d.min}</strong></span>
        <span>moy <strong>{d.moyenne}</strong></span>
        <span>max <strong>{d.max}</strong></span>
      </div>
      {/* Barre etendue min -> max avec repere sur la moyenne */}
      <div style={barreEqFondStyle}>
        <div style={{ ...barreEqRepereStyle, left: `${posMoy}%` }} />
      </div>
      <div style={ecartTypeStyle}>
        écart-type : <strong>{d.ecart_type}</strong> {unite}
      </div>
    </div>
  );
}

// --- Table detail par tournee ---
function TableTournees({ tournees, volMin, volMax, distMin, distMax }) {
  return (
    <table style={tableStyle}>
      <thead>
        <tr>
          <th style={thStyle}>Tournée</th>
          <th style={thStyle}>Véhicule</th>
          <th style={thStyle}>Charge (m³)</th>
          <th style={thStyle}>Capacité (m³)</th>
          <th style={{ ...thStyle, width: "28%" }}>Remplissage</th>
          <th style={thStyle}>Distance (km)</th>
        </tr>
      </thead>
      <tbody>
        {tournees.map((t) => (
          <tr key={t.id_tournee}>
            <td style={tdStyle}>{t.id_tournee}</td>
            <td style={tdStyle}>{t.id_vehicule}</td>
            <td style={tdStyle}>
              {t.charge_volume}
              {t.charge_volume === volMax && <Tag texte="max" />}
              {t.charge_volume === volMin && <Tag texte="min" doux />}
            </td>
            <td style={tdStyle}>{t.capacite}</td>
            <td style={tdStyle}>
              <BarreRemplissage pct={t.remplissage_pct} />
            </td>
            <td style={tdStyle}>
              {t.distance_km}
              {t.distance_km === distMax && <Tag texte="max" />}
              {t.distance_km === distMin && <Tag texte="min" doux />}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Barre de remplissage : largeur = %, couleur informative (pas un verdict).
function BarreRemplissage({ pct }) {
  const largeur = Math.max(0, Math.min(100, pct));
  const couleur = pct >= 85 ? "#2e7d32" : pct >= 50 ? "#1565c0" : "#e08a00";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={barreRemplFondStyle}>
        <div style={{ ...barreRemplPleinStyle, width: `${largeur}%`, background: couleur }} />
      </div>
      <span style={{ fontSize: 12, minWidth: 46 }}>{pct} %</span>
    </div>
  );
}

// Petit marqueur min / max sur les extremes d'equilibrage.
function Tag({ texte, doux }) {
  return (
    <span
      style={{
        marginLeft: 6,
        fontSize: 11,
        padding: "1px 6px",
        borderRadius: 4,
        background: doux ? "#eef4fb" : "#fff4e5",
        color: doux ? "#1565c0" : "#b26a00",
        border: `1px solid ${doux ? "#cfe0f3" : "#f0d9b5"}`,
      }}
    >
      {texte}
    </span>
  );
}

// --- Styles (alignes sur RunDetail : sans-serif, bleu #1565c0, radius 8) ---
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

const lienRetourStyle = { textDecoration: "none", color: "#1565c0", fontSize: 14 };

const lienDetailStyle = {
  textDecoration: "none",
  color: "#1565c0",
  fontSize: 14,
  fontWeight: "bold",
};

const selectStyle = {
  fontSize: 14,
  padding: "4px 8px",
  borderRadius: 6,
  border: "1px solid #cfe0f3",
  background: "#fff",
};

const corpsStyle = { flex: 1, padding: 16, overflow: "auto" };

const cartesRangeeStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  marginBottom: 20,
};

const carteKpiStyle = {
  flex: "1 1 160px",
  minWidth: 150,
  padding: "12px 14px",
  background: "#eef4fb",
  border: "1px solid #cfe0f3",
  borderRadius: 8,
};

const carteTitreStyle = {
  fontSize: 13,
  color: "#5a6b7b",
  marginBottom: 6,
};

const carteValeurStyle = {
  fontSize: 26,
  fontWeight: "bold",
  lineHeight: 1.1,
};

const carteSousStyle = { fontSize: 12, color: "#5a6b7b", marginTop: 4 };

const sectionTitreStyle = {
  fontSize: 15,
  fontWeight: "bold",
  margin: "8px 0 12px",
  color: "#333",
};

const panneauEqStyle = {
  flex: "1 1 260px",
  minWidth: 240,
  padding: "12px 14px",
  border: "1px solid #ddd",
  borderRadius: 8,
  background: "#fff",
};

const eqLigneStyle = {
  display: "flex",
  justifyContent: "space-between",
  fontSize: 13,
  margin: "4px 0 8px",
};

const barreEqFondStyle = {
  position: "relative",
  height: 8,
  borderRadius: 4,
  background: "linear-gradient(90deg,#cfe0f3,#1565c0)",
};

const barreEqRepereStyle = {
  position: "absolute",
  top: -3,
  width: 2,
  height: 14,
  background: "#c62828",
  transform: "translateX(-1px)",
};

const ecartTypeStyle = { fontSize: 12, color: "#5a6b7b", marginTop: 8 };

const barreRemplFondStyle = {
  flex: 1,
  height: 10,
  borderRadius: 5,
  background: "#eee",
  overflow: "hidden",
};

const barreRemplPleinStyle = { height: "100%", borderRadius: 5 };

const tableStyle = { width: "100%", borderCollapse: "collapse", fontSize: 13 };

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