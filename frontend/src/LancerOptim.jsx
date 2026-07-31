import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Garde-fou client : au-dessus de la borne de requete du back (120 s). Si le
// solve depasse, on coupe cote client plutot que de laisser l'onglet pendu
// indefiniment. fetch natif n'a pas de timeout par defaut, d'ou l'AbortController.
const TIMEOUT_MS = 130_000;

export default function LancerOptim() {
  const [etat, setEtat] = useState("pret"); // pret | encours | ok | erreur
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState(null); // { texte, anomalies? }
  const [secondes, setSecondes] = useState(0);
  const chronoRef = useRef(null);

  // Chrono d'attente : purement cosmetique, rassure pendant les ~45 s de solve.
  useEffect(() => {
    if (etat === "encours") {
      setSecondes(0);
      chronoRef.current = setInterval(() => setSecondes((s) => s + 1), 1000);
    } else {
      clearInterval(chronoRef.current);
    }
    return () => clearInterval(chronoRef.current);
  }, [etat]);

  async function lancer() {
    setEtat("encours");
    setResultat(null);
    setErreur(null);

    const controleur = new AbortController();
    const minuteur = setTimeout(() => controleur.abort(), TIMEOUT_MS);

    try {
      const r = await fetch(`${API_URL}/optimisations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}), // corps optionnel vide -> defaut 45 s cote back
        signal: controleur.signal,
      });

      const corps = await r.json().catch(() => null);

      if (!r.ok) {
        setErreur(messageErreur(r.status, corps));
        setEtat("erreur");
        return;
      }

      setResultat(corps);
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

  return (
    <div style={pageStyle}>
      <div style={barreStyle}>
        <Link to="/" style={lienRetourStyle}>← Carte</Link>
        <span style={titreStyle}>Lancer une optimisation</span>
      </div>

      <div style={corpsStyle}>
        <p style={introStyle}>
          Lance le solveur sur l'état courant de la base (lots, flotte, dépôts)
          et crée un nouveau run. Le calcul est synchrone et prend jusqu'à
          ~45&nbsp;s ; ne ferme pas l'onglet pendant l'attente.
        </p>

        <button
          type="button"
          onClick={lancer}
          disabled={etat === "encours"}
          style={etat === "encours" ? boutonOccupeStyle : boutonStyle}
        >
          {etat === "encours"
            ? `Optimisation en cours… ${secondes} s`
            : "Lancer l'optimisation"}
        </button>

        {etat === "erreur" && erreur && <BlocErreur erreur={erreur} />}
        {etat === "ok" && resultat && <BlocResultat resultat={resultat} />}
      </div>
    </div>
  );
}

// --- Normalise la reponse d'erreur du back en { texte, anomalies? } ---
// 409 : detail = { message, anomalies: [...] }   (donnees a corriger)
// 422 : detail = chaine                           (donnees insuffisantes)
// 500 : detail = chaine                           (echec solveur / persistance)
function messageErreur(status, corps) {
  const detail = corps?.detail;

  if (status === 409 && detail && typeof detail === "object") {
    return {
      texte: detail.message ?? "Données à corriger avant optimisation.",
      anomalies: detail.anomalies ?? [],
    };
  }
  if (typeof detail === "string") return { texte: detail };
  return { texte: `Erreur HTTP ${status}.` };
}

// --- Bloc d'erreur : message + liste d'anomalies si presente (cas 409) ---
function BlocErreur({ erreur }) {
  return (
    <div style={boiteErreurStyle}>
      <strong>Échec :</strong> {erreur.texte}
      {erreur.anomalies && erreur.anomalies.length > 0 && (
        <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
          {erreur.anomalies.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// --- Bloc de resultat : resume + avertissements + liens vers les ecrans ---
function BlocResultat({ resultat }) {
  const {
    id_run,
    distance_totale_km,
    nb_tournees,
    nb_lots_servis,
    nb_lots_non_servis,
    lots_non_servis = [],
    avertissements = [],
  } = resultat;

  return (
    <div style={{ marginTop: 20 }}>
      <p style={succesStyle}>✓ Run {id_run} créé.</p>

      <div style={resumeStyle}>
        <span><strong>{nb_tournees}</strong> tournées</span>
        <span><strong>{nb_lots_servis}</strong> lots servis</span>
        <span><strong>{nb_lots_non_servis}</strong> non servis</span>
        <span><strong>{distance_totale_km}</strong> km au total</span>
      </div>

      {/* Avertissements '[info]' : lots abandonnes par construction (depot sans
          vehicule au caisson requis). Informatif, pas une erreur. */}
      {avertissements.length > 0 && (
        <div style={boiteInfoStyle}>
          <strong>Avertissements ({avertissements.length})</strong>
          <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
            {avertissements.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Detail des lots non servis, si le solveur en a abandonne */}
      {lots_non_servis.length > 0 && (
        <p style={{ fontSize: 13, color: "#555", marginTop: 12 }}>
          Lots non servis : {lots_non_servis.join(", ")}
        </p>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
        <Link to={`/runs/${id_run}`} style={lienDetailStyle}>
          Voir le détail →
        </Link>
        <Link to="/" style={lienCarteStyle}>
          Voir sur la carte →
        </Link>
      </div>
    </div>
  );
}

// --- Styles (coherents avec RunDetail / CarteView) ---
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

const corpsStyle = { flex: 1, padding: 16, overflow: "auto", maxWidth: 720 };

const introStyle = {
  fontSize: 14,
  color: "#444",
  lineHeight: 1.5,
  marginTop: 0,
  marginBottom: 20,
};

const boutonStyle = {
  background: "#2e7d32",
  color: "white",
  border: "none",
  borderRadius: 6,
  padding: "10px 20px",
  fontSize: 15,
  cursor: "pointer",
  fontFamily: "sans-serif",
};

const boutonOccupeStyle = {
  ...boutonStyle,
  background: "#9e9e9e",
  cursor: "default",
};

const succesStyle = {
  fontSize: 16,
  fontWeight: "bold",
  color: "#2e7d32",
  margin: "0 0 12px",
};

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
