import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Carte from "./Carte";

// URL de l'API : variable d'env Vite, avec repli sur le localhost de dev
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Libelle lisible d'un run dans le selecteur
function libelleRun(r) {
  const date = new Date(r.date_calcul).toLocaleDateString("fr-FR");
  const ns =
    r.nb_lots_non_servis > 0 ? `, ${r.nb_lots_non_servis} non servis` : "";
  return `Run ${r.id_run} — ${r.nb_tournees} tournées, ${r.nb_lots_servis} lots${ns}, ${r.distance_totale_km} km (${date})`;
}

export default function CarteView() {
  const [runs, setRuns] = useState(null); // null = chargement, [] = aucun run
  const [erreur, setErreur] = useState(null);
  const [idRun, setIdRun] = useState(null);
  const [pleinEcran, setPleinEcran] = useState(false);

  // Charger la liste des runs au montage ; selectionner le plus recent
  useEffect(() => {
    fetch(`${API_URL}/runs`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((liste) => {
        setRuns(liste);
        if (liste.length > 0) setIdRun(liste[0].id_run); // API triee : plus recent d'abord
      })
      .catch((e) => setErreur(e.message));
  }, []);

  return (
    <div style={pageStyle}>
      {/* Barre du haut : masquee en plein ecran */}
      {!pleinEcran && (
        <div style={barreStyle}>
          <span style={titreStyle}>Carte des tournées</span>

          {erreur && (
            <span style={{ color: "#c62828" }}>Erreur : {erreur}</span>
          )}
          {runs === null && !erreur && <span>Chargement des runs…</span>}
          {runs !== null && runs.length === 0 && (
            <span>Aucun run disponible</span>
          )}
          {runs !== null && runs.length > 0 && (
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              Run :
              <select
                value={idRun ?? ""}
                onChange={(e) => setIdRun(Number(e.target.value))}
                style={selectStyle}
              >
                {runs.map((r) => (
                  <option key={r.id_run} value={r.id_run}>
                    {libelleRun(r)}
                  </option>
                ))}
              </select>
            </label>
          )}

          {/* Actions, poussees a droite de la barre.
              "Saisir des lots" est l'entree principale (creer + optimiser une
              vague) ; "Optimiser tous les lots" relance le solveur sur toute
              la base ; "Tableau de bord" et "Detail" dependent du run
              selectionne (ils transmettent / suivent le run courant). */}
          <div style={actionsStyle}>
            <Link to="/saisie" style={lienSaisirStyle}>
              + Saisir des lots
            </Link>
            <Link to="/lancer" style={lienLancerStyle}>
              Optimiser tous les lots
            </Link>
            {idRun != null && (
              <Link to={`/kpis?run=${idRun}`} style={lienKpisStyle}>
                Tableau de bord
              </Link>
            )}
            {idRun != null && (
              <Link to={`/runs/${idRun}`} style={lienDetailStyle}>
                Détail →
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Zone carte : carte en mode reduit, ou fixe plein ecran */}
      <div style={pleinEcran ? carteWrapperPlein : carteWrapperReduit}>
        {idRun != null ? (
          <Carte idRun={idRun} />
        ) : (
          <div style={{ padding: 20 }}>
            {erreur
              ? `Erreur : ${erreur}`
              : "Sélectionne un run pour afficher la carte."}
          </div>
        )}

        {idRun != null && (
          <button
            type="button"
            onClick={() => setPleinEcran((v) => !v)}
            style={boutonPleinEcranStyle}
            title={pleinEcran ? "Réduire" : "Plein écran"}
          >
            {pleinEcran ? "⤢ Réduire" : "⛶ Plein écran"}
          </button>
        )}
      </div>
    </div>
  );
}

// --- Styles ---
const pageStyle = {
  display: "flex",
  flexDirection: "column",
  height: "100vh",
  width: "100%",
};

const barreStyle = {
  display: "flex",
  alignItems: "center",
  gap: 16,
  padding: "10px 16px",
  borderBottom: "1px solid #ddd",
  background: "#fafafa",
  fontFamily: "sans-serif",
  fontSize: 14,
  flexShrink: 0,
};

const titreStyle = {
  fontWeight: "bold",
  fontSize: 16,
};

const selectStyle = {
  fontSize: 14,
  padding: "4px 6px",
  minWidth: 320,
};

// Groupe d'actions pousse a droite de la barre
const actionsStyle = {
  marginLeft: "auto",
  display: "flex",
  alignItems: "center",
  gap: 8,
};

// Action principale : saisir une vague de lots (vert)
const lienSaisirStyle = {
  textDecoration: "none",
  background: "#2e7d32",
  color: "white",
  borderRadius: 6,
  padding: "6px 12px",
  fontFamily: "sans-serif",
  fontSize: 13,
  whiteSpace: "nowrap",
};

// Action secondaire : optimiser toute la base (contour)
const lienLancerStyle = {
  textDecoration: "none",
  background: "white",
  color: "#2e7d32",
  border: "1px solid #a5d6a7",
  borderRadius: 6,
  padding: "6px 12px",
  fontFamily: "sans-serif",
  fontSize: 13,
  whiteSpace: "nowrap",
};

// Lien "Tableau de bord" : meme famille bleue que Detail, en contour
// (tous deux "consultent" le run courant), pour ne pas voler la vedette a
// l'action principale verte.
const lienKpisStyle = {
  textDecoration: "none",
  background: "white",
  color: "#1565c0",
  border: "1px solid #90caf9",
  borderRadius: 6,
  padding: "6px 12px",
  fontFamily: "sans-serif",
  fontSize: 13,
  whiteSpace: "nowrap",
};

// Lien "Detail" (positionnement gere par actionsStyle)
const lienDetailStyle = {
  textDecoration: "none",
  background: "#1565c0",
  color: "white",
  borderRadius: 6,
  padding: "6px 12px",
  fontFamily: "sans-serif",
  fontSize: 13,
  whiteSpace: "nowrap",
};

// Mode reduit : la carte occupe le reste de la page, en "carte" (bord + ombre)
const carteWrapperReduit = {
  flex: 1,
  minHeight: 0, // indispensable en flex column pour que la carte ait une hauteur
  position: "relative",
  margin: 12,
  borderRadius: 8,
  overflow: "hidden",
  border: "1px solid #ccc",
  boxShadow: "0 1px 6px rgba(0,0,0,0.15)",
};

// Mode plein ecran : recouvre tout le viewport
const carteWrapperPlein = {
  position: "fixed",
  inset: 0,
  zIndex: 2000,
  background: "white",
};

const boutonPleinEcranStyle = {
  position: "absolute",
  bottom: 12,
  left: 12,
  zIndex: 1200, // au-dessus du panneau de couches de la carte
  background: "white",
  border: "1px solid #999",
  borderRadius: 6,
  padding: "6px 10px",
  fontFamily: "sans-serif",
  fontSize: 13,
  cursor: "pointer",
  boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
};