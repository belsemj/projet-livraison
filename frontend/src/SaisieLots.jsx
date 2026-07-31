import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Garde-fou client au-dessus de la borne de requete du back (120 s).
const TIMEOUT_MS = 130_000;

const CAISSONS = ["standard", "refrigere", "securise"];

// Une ligne de lot vierge
const ligneVide = () => ({
  volume: "",
  caisson_requis: "standard",
  id_station_source: "",
  id_destination: "",
});

export default function SaisieLots() {
  // Referentiels fixes (base) pour les listes deroulantes
  const [stations, setStations] = useState([]);
  const [destinations, setDestinations] = useState([]);
  const [refErreur, setRefErreur] = useState(null);

  const [lignes, setLignes] = useState([ligneVide()]);
  const [nombre, setNombre] = useState(1);

  const [etat, setEtat] = useState("pret"); // pret | encours | ok | erreur
  const [phase, setPhase] = useState(""); // libelle d'etape pendant "encours"
  const [resultat, setResultat] = useState(null); // { ...run, id_vague, total }
  const [erreur, setErreur] = useState(null); // { texte, details? }
  const [secondes, setSecondes] = useState(0);
  const chronoRef = useRef(null);

  // --- Charger les referentiels au montage ---
  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/stations/`).then((r) => {
        if (!r.ok) throw new Error(`stations : HTTP ${r.status}`);
        return r.json();
      }),
      fetch(`${API_URL}/destinations/?limit=1000`).then((r) => {
        if (!r.ok) throw new Error(`destinations : HTTP ${r.status}`);
        return r.json();
      }),
    ])
      .then(([st, de]) => {
        setStations(st);
        setDestinations(de);
      })
      .catch((e) => setRefErreur(e.message));
  }, []);

  // --- Chrono d'attente pendant l'optimisation ---
  useEffect(() => {
    if (etat === "encours") {
      setSecondes(0);
      chronoRef.current = setInterval(() => setSecondes((s) => s + 1), 1000);
    } else {
      clearInterval(chronoRef.current);
    }
    return () => clearInterval(chronoRef.current);
  }, [etat]);

  // --- Edition des lignes ---
  const majLigne = (i, champ, valeur) =>
    setLignes((prec) =>
      prec.map((l, k) => (k === i ? { ...l, [champ]: valeur } : l))
    );
  const ajouterLigne = () => setLignes((prec) => [...prec, ligneVide()]);
  const retirerLigne = (i) =>
    setLignes((prec) => (prec.length > 1 ? prec.filter((_, k) => k !== i) : prec));
  const genererLignes = () => {
    const n = Math.max(1, Math.min(200, Number(nombre) || 1));
    setLignes(Array.from({ length: n }, ligneVide));
  };

  // --- Validation locale avant envoi ---
  function validerLignes() {
    for (let i = 0; i < lignes.length; i++) {
      const l = lignes[i];
      if (!(Number(l.volume) > 0)) return `Lot ${i + 1} : volume manquant ou ≤ 0.`;
      if (!l.id_station_source) return `Lot ${i + 1} : dépôt source manquant.`;
      if (!l.id_destination) return `Lot ${i + 1} : destination manquante.`;
    }
    return null;
  }

  // --- Auto : creer la vague puis l'optimiser ---
  async function optimiser() {
    const probleme = validerLignes();
    if (probleme) {
      setErreur({ texte: probleme });
      setEtat("erreur");
      return;
    }

    setEtat("encours");
    setErreur(null);
    setResultat(null);

    const controleur = new AbortController();
    const minuteur = setTimeout(() => controleur.abort(), TIMEOUT_MS);

    const lots = lignes.map((l) => ({
      volume: Number(l.volume),
      caisson_requis: l.caisson_requis,
      id_station_source: Number(l.id_station_source),
      id_destination: Number(l.id_destination),
    }));

    try {
      // 1. Persister la vague
      setPhase("Enregistrement de la vague…");
      const rv = await fetch(`${API_URL}/vagues`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lots }),
        signal: controleur.signal,
      });
      const corpsV = await rv.json().catch(() => null);
      if (!rv.ok) {
        setErreur(messageErreur(rv.status, corpsV));
        setEtat("erreur");
        return;
      }
      const { id_vague } = corpsV;

      // 2. Optimiser cette vague
      setPhase("Optimisation en cours…");
      const ro = await fetch(`${API_URL}/optimisations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_vague }),
        signal: controleur.signal,
      });
      const corpsO = await ro.json().catch(() => null);
      if (!ro.ok) {
        setErreur(messageErreur(ro.status, corpsO));
        setEtat("erreur");
        return;
      }

      setResultat({ ...corpsO, id_vague, total: lots.length });
      setEtat("ok");
    } catch (e) {
      setErreur({
        texte:
          e.name === "AbortError"
            ? `Délai dépassé (> ${TIMEOUT_MS / 1000} s) : le serveur n'a pas répondu.`
            : `Échec réseau : ${e.message}`,
      });
      setEtat("erreur");
    } finally {
      clearTimeout(minuteur);
    }
  }

  const occupe = etat === "encours";

  return (
    <div style={pageStyle}>
      <div style={barreStyle}>
        <Link to="/" style={lienRetourStyle}>← Carte</Link>
        <span style={titreStyle}>Saisir des lots à livrer</span>
      </div>

      <div style={corpsStyle}>
        <p style={introStyle}>
          Renseigne les lots d'une nouvelle vague. Les dépôts et destinations
          sont ceux de la base (listes déroulantes). Le solveur optimisera cette
          vague uniquement, sans toucher aux données existantes.
        </p>

        {refErreur && (
          <p style={{ color: "#c62828" }}>
            Impossible de charger les référentiels : {refErreur}
          </p>
        )}

        {/* Generateur de lignes */}
        <div style={genStyle}>
          <label>
            Nombre de lots :{" "}
            <input
              type="number"
              min={1}
              max={200}
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              style={champNombreStyle}
              disabled={occupe}
            />
          </label>
          <button type="button" onClick={genererLignes} style={boutonSecondaireStyle} disabled={occupe}>
            Générer les lignes
          </button>
        </div>

        {/* Tableau de saisie */}
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>#</th>
              <th style={thStyle}>Volume (m³)</th>
              <th style={thStyle}>Caisson</th>
              <th style={thStyle}>Dépôt source</th>
              <th style={thStyle}>Destination</th>
              <th style={thStyle}></th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((l, i) => (
              <tr key={i}>
                <td style={tdStyle}>{i + 1}</td>
                <td style={tdStyle}>
                  <input
                    type="number"
                    min={0.01}
                    step={0.01}
                    value={l.volume}
                    onChange={(e) => majLigne(i, "volume", e.target.value)}
                    style={champVolumeStyle}
                    disabled={occupe}
                  />
                </td>
                <td style={tdStyle}>
                  <select
                    value={l.caisson_requis}
                    onChange={(e) => majLigne(i, "caisson_requis", e.target.value)}
                    style={selectStyle}
                    disabled={occupe}
                  >
                    {CAISSONS.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </td>
                <td style={tdStyle}>
                  <select
                    value={l.id_station_source}
                    onChange={(e) => majLigne(i, "id_station_source", e.target.value)}
                    style={selectStyle}
                    disabled={occupe}
                  >
                    <option value="">— choisir —</option>
                    {stations.map((s) => (
                      <option key={s.id_station} value={s.id_station}>
                        {s.nom} ({s.gouvernorat})
                      </option>
                    ))}
                  </select>
                </td>
                <td style={tdStyle}>
                  <select
                    value={l.id_destination}
                    onChange={(e) => majLigne(i, "id_destination", e.target.value)}
                    style={selectStyle}
                    disabled={occupe}
                  >
                    <option value="">— choisir —</option>
                    {destinations.map((d) => (
                      <option key={d.id_destination} value={d.id_destination}>
                        {d.nom} ({d.gouvernorat})
                      </option>
                    ))}
                  </select>
                </td>
                <td style={tdStyle}>
                  <button
                    type="button"
                    onClick={() => retirerLigne(i)}
                    style={boutonRetirerStyle}
                    disabled={occupe || lignes.length === 1}
                    title="Retirer ce lot"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <button type="button" onClick={ajouterLigne} style={boutonSecondaireStyle} disabled={occupe}>
          + Ajouter un lot
        </button>

        {/* Actions : auto (Phase 1) et manuel (Phase 2, a venir) */}
        <div style={actionsStyle}>
          <button
            type="button"
            onClick={optimiser}
            disabled={occupe}
            style={occupe ? boutonOccupeStyle : boutonPrincipalStyle}
          >
            {occupe ? `${phase} ${secondes} s` : "Optimiser automatiquement"}
          </button>

          <button
            type="button"
            disabled
            style={boutonDesactiveStyle}
            title="Affectation manuelle : disponible en Phase 2"
          >
            Affectation manuelle (à venir)
          </button>
        </div>

        {etat === "erreur" && erreur && <BlocErreur erreur={erreur} />}
        {etat === "ok" && resultat && <BlocResultat resultat={resultat} />}
      </div>
    </div>
  );
}

// --- Normalisation des erreurs back en { texte, details? } ---
function messageErreur(status, corps) {
  const detail = corps?.detail;

  // 400 vague : { message, destinations_inconnues, stations_inconnues }
  if (status === 400 && detail && typeof detail === "object") {
    const bouts = [];
    if (detail.destinations_inconnues?.length)
      bouts.push(`destinations inconnues : ${detail.destinations_inconnues.join(", ")}`);
    if (detail.stations_inconnues?.length)
      bouts.push(`dépôts inconnus : ${detail.stations_inconnues.join(", ")}`);
    return { texte: detail.message ?? "Référence invalide.", details: bouts };
  }
  // 409 optimisation : { message, anomalies: [...] }
  if (status === 409 && detail && typeof detail === "object") {
    return { texte: detail.message ?? "Données à corriger.", details: detail.anomalies ?? [] };
  }
  // 422 / 500 : detail = chaine
  if (typeof detail === "string") return { texte: detail };
  return { texte: `Erreur HTTP ${status}.` };
}

function BlocErreur({ erreur }) {
  return (
    <div style={boiteErreurStyle}>
      <strong>Échec :</strong> {erreur.texte}
      {erreur.details && erreur.details.length > 0 && (
        <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
          {erreur.details.map((d, i) => <li key={i}>{d}</li>)}
        </ul>
      )}
    </div>
  );
}

function BlocResultat({ resultat }) {
  const {
    id_run, id_vague, total,
    distance_totale_km, nb_tournees,
    nb_lots_servis, nb_lots_non_servis,
    lots_non_servis = [], avertissements = [],
  } = resultat;

  return (
    <div style={{ marginTop: 24 }}>
      <p style={succesStyle}>✓ Run {id_run} créé pour la vague {id_vague}.</p>

      {/* Parametres de performance */}
      <div style={resumeStyle}>
        <span><strong>{nb_tournees}</strong> tournées</span>
        <span><strong>{nb_lots_servis}</strong>/{total} lots servis</span>
        <span><strong>{nb_lots_non_servis}</strong> non servis</span>
        <span><strong>{distance_totale_km}</strong> km au total</span>
      </div>

      {avertissements.length > 0 && (
        <div style={boiteInfoStyle}>
          <strong>Avertissements ({avertissements.length})</strong>
          <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
            {avertissements.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      {lots_non_servis.length > 0 && (
        <p style={{ fontSize: 13, color: "#555", marginTop: 12 }}>
          Lots non servis : {lots_non_servis.join(", ")}
        </p>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
        <Link to={`/runs/${id_run}`} style={lienDetailStyle}>Voir le détail →</Link>
        <Link to="/" style={lienCarteStyle}>Voir sur la carte →</Link>
      </div>
    </div>
  );
}

// --- Styles (coherents avec RunDetail / CarteView / LancerOptim) ---
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
const corpsStyle = { flex: 1, padding: 16, overflow: "auto", maxWidth: 900 };
const introStyle = { fontSize: 14, color: "#444", lineHeight: 1.5, marginTop: 0, marginBottom: 20 };

const genStyle = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  marginBottom: 16,
  fontSize: 14,
};

const champNombreStyle = { width: 70, padding: "4px 6px", fontSize: 14 };
const champVolumeStyle = { width: 90, padding: "4px 6px", fontSize: 13 };
const selectStyle = { fontSize: 13, padding: "4px 6px", minWidth: 160 };

const tableStyle = { width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 12 };
const thStyle = {
  textAlign: "left",
  padding: "6px 10px",
  borderBottom: "1px solid #ddd",
  background: "#fafafa",
  fontWeight: "bold",
};
const tdStyle = { padding: "6px 10px", borderBottom: "1px solid #f0f0f0" };

const actionsStyle = { display: "flex", gap: 12, marginTop: 20, flexWrap: "wrap" };

const boutonPrincipalStyle = {
  background: "#2e7d32",
  color: "white",
  border: "none",
  borderRadius: 6,
  padding: "10px 20px",
  fontSize: 15,
  cursor: "pointer",
  fontFamily: "sans-serif",
};
const boutonOccupeStyle = { ...boutonPrincipalStyle, background: "#9e9e9e", cursor: "default" };
const boutonDesactiveStyle = {
  background: "#eee",
  color: "#999",
  border: "1px solid #ddd",
  borderRadius: 6,
  padding: "10px 20px",
  fontSize: 15,
  cursor: "not-allowed",
  fontFamily: "sans-serif",
};
const boutonSecondaireStyle = {
  background: "white",
  color: "#1565c0",
  border: "1px solid #cfe0f3",
  borderRadius: 6,
  padding: "6px 12px",
  fontSize: 13,
  cursor: "pointer",
  fontFamily: "sans-serif",
};
const boutonRetirerStyle = {
  background: "white",
  color: "#c62828",
  border: "1px solid #f5c6c2",
  borderRadius: 4,
  padding: "2px 8px",
  fontSize: 13,
  cursor: "pointer",
};

const succesStyle = { fontSize: 16, fontWeight: "bold", color: "#2e7d32", margin: "0 0 12px" };
const resumeStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 24,
  padding: "10px 14px",
  background: "#eef4fb",
  border: "1px solid #cfe0f3",
  borderRadius: 8,
  fontSize: 14,
};
const boiteInfoStyle = {
  marginTop: 12,
  padding: "10px 14px",
  background: "#fff8e1",
  border: "1px solid #ffe082",
  borderRadius: 8,
  fontSize: 13,
  color: "#5f4b00",
};
const boiteErreurStyle = {
  marginTop: 20,
  padding: "10px 14px",
  background: "#fdecea",
  border: "1px solid #f5c6c2",
  borderRadius: 8,
  fontSize: 14,
  color: "#611a15",
};
const lienDetailStyle = {
  textDecoration: "none",
  background: "#1565c0",
  color: "white",
  borderRadius: 6,
  padding: "8px 14px",
  fontSize: 13,
};
const lienCarteStyle = {
  textDecoration: "none",
  background: "#eef4fb",
  color: "#1565c0",
  border: "1px solid #cfe0f3",
  borderRadius: 6,
  padding: "8px 14px",
  fontSize: 13,
};
