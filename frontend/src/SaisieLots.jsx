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
  const [vehicules, setVehicules] = useState([]);
  const [chauffeurs, setChauffeurs] = useState([]);
  const [refErreur, setRefErreur] = useState(null);

  const [lignes, setLignes] = useState([ligneVide()]);
  const [nombre, setNombre] = useState(1);

  // Vue courante : saisie (Phase 1 + point d'entree manuel) ou affectation (Phase 2)
  const [vue, setVue] = useState("saisie"); // saisie | affectation

  const [etat, setEtat] = useState("pret"); // pret | encours | ok | erreur
  const [phase, setPhase] = useState(""); // libelle d'etape pendant "encours"
  const [resultat, setResultat] = useState(null); // resultat AUTO : { ...run, id_vague, total }
  const [erreur, setErreur] = useState(null); // { texte, details? }
  const [secondes, setSecondes] = useState(0);
  const chronoRef = useRef(null);

  // Mode manuel : vague persistee + affectation lot -> couple
  const [idVague, setIdVague] = useState(null);
  // affect : [{ id_lot, volume, caisson_requis, id_station_source, id_destination,
  //             id_vehicule: number|"", id_chauffeur: number|"" }]
  const [affect, setAffect] = useState([]);
  const [evaluation, setEvaluation] = useState(null); // resultat MANUEL : EvaluationResultat
  const [evalPerimee, setEvalPerimee] = useState(false); // affectation modifiee depuis la derniere eval

  // --- Charger les referentiels au montage ---
  // Chargements DECOUPLES (allSettled) : un endpoint en panne ne doit pas vider
  // les autres. Chaque echec est nomme precisement dans refErreur.
  useEffect(() => {
    const charger = async (chemin, label) => {
      const r = await fetch(`${API_URL}${chemin}`);
      if (!r.ok) throw new Error(`${label} : HTTP ${r.status}`);
      return r.json();
    };

    const sources = [
      ["/stations/", "stations", setStations],
      ["/destinations/?limit=1000", "destinations", setDestinations],
      ["/vehicules/?limit=1000", "vehicules", setVehicules],
      ["/chauffeurs/?limit=1000", "chauffeurs", setChauffeurs],
    ];

    Promise.allSettled(
      sources.map(([chemin, label]) => charger(chemin, label))
    ).then((res) => {
      const echecs = [];
      res.forEach((r, i) => {
        const [, label, set] = sources[i];
        if (r.status === "fulfilled") set(r.value);
        else echecs.push(`${label} (${r.reason?.message ?? "injoignable"})`);
      });
      setRefErreur(echecs.length ? echecs.join(" ; ") : null);
    });
  }, []);

  // --- Chrono d'attente pendant les appels serveur ---
  useEffect(() => {
    if (etat === "encours") {
      setSecondes(0);
      chronoRef.current = setInterval(() => setSecondes((s) => s + 1), 1000);
    } else {
      clearInterval(chronoRef.current);
    }
    return () => clearInterval(chronoRef.current);
  }, [etat]);

  // --- Edition des lignes (saisie) ---
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

  // Construit la charge utile "lots" a partir des lignes saisies.
  const construireLots = () =>
    lignes.map((l) => ({
      volume: Number(l.volume),
      caisson_requis: l.caisson_requis,
      id_station_source: Number(l.id_station_source),
      id_destination: Number(l.id_destination),
    }));

  // --- Helpers d'affichage (petits referentiels : find suffit) ---
  const nomStation = (id) =>
    stations.find((s) => s.id_station === id)?.nom ?? `dépôt ${id}`;
  const nomChauffeur = (id) =>
    chauffeurs.find((c) => c.id_chauffeur === id)?.nom ?? `chauffeur ${id}`;
  const nomDestination = (id) =>
    destinations.find((d) => d.id_destination === id)?.nom ?? `dest. ${id}`;
  const vehiculeById = (id) => vehicules.find((v) => v.id_vehicule === id);
  const destinationDuLot = (idLot) =>
    affect.find((r) => r.id_lot === idLot)?.id_destination;

  // Vehicules proposables : ecartes hors_service et sans binome (couple impossible).
  // On garde les "reserve" : le mode manuel sert justement a tester des scenarios.
  const vehiculesAffectables = vehicules
    .filter((v) => v.statut !== "hors_service" && v.id_chauffeur != null)
    .slice()
    .sort((a, b) => a.id_vehicule - b.id_vehicule);

  const libelleVehicule = (v) =>
    `V${v.id_vehicule} · ${v.type_caisson} · ${v.capacite} m³ · ` +
    `${nomStation(v.id_station)} · ${nomChauffeur(v.id_chauffeur)}`;

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
    setEvaluation(null);

    const controleur = new AbortController();
    const minuteur = setTimeout(() => controleur.abort(), TIMEOUT_MS);
    const lots = construireLots();

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

  // --- Manuel : persister la vague puis passer en affectation ---
  // Les lots n'ont d'id qu'apres persistance : on cree la vague, on apparie les
  // id_lots renvoyes (memes ordre que les lignes) et on bascule de vue.
  async function preparerAffectation() {
    const probleme = validerLignes();
    if (probleme) {
      setErreur({ texte: probleme });
      setEtat("erreur");
      return;
    }

    setEtat("encours");
    setPhase("Enregistrement de la vague…");
    setErreur(null);
    setResultat(null);
    setEvaluation(null);

    const controleur = new AbortController();
    const minuteur = setTimeout(() => controleur.abort(), TIMEOUT_MS);
    const lots = construireLots();

    try {
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
      const { id_vague, id_lots } = corpsV;

      // Appariement par index : id_lots suit l'ordre des lignes saisies.
      const rangs = lignes.map((l, i) => ({
        id_lot: id_lots[i],
        volume: Number(l.volume),
        caisson_requis: l.caisson_requis,
        id_station_source: Number(l.id_station_source),
        id_destination: Number(l.id_destination),
        id_vehicule: "",
        id_chauffeur: "",
      }));

      setIdVague(id_vague);
      setAffect(rangs);
      setVue("affectation");
      setEtat("pret");
      setPhase("");
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

  // Choix vehicule : le chauffeur est pre-rempli avec le binome, modifiable.
  const majAffectVehicule = (i, val) => {
    setEvalPerimee(true);
    setAffect((prec) =>
      prec.map((r, k) => {
        if (k !== i) return r;
        if (val === "") return { ...r, id_vehicule: "", id_chauffeur: "" };
        const idv = Number(val);
        const v = vehiculeById(idv);
        return { ...r, id_vehicule: idv, id_chauffeur: v?.id_chauffeur ?? "" };
      })
    );
  };

  // Remplacement manuel du chauffeur du couple.
  const majAffectChauffeur = (i, val) => {
    setEvalPerimee(true);
    setAffect((prec) =>
      prec.map((r, k) =>
        k === i ? { ...r, id_chauffeur: val === "" ? "" : Number(val) } : r
      )
    );
  };

  // Retour a la saisie. La vague deja persistee reste en base (orpheline,
  // sans run) ; nettoyable via scripts/supprimer_lots_test.py au besoin.
  const retourSaisie = () => {
    setVue("saisie");
    setIdVague(null);
    setAffect([]);
    setEvaluation(null);
    setEvalPerimee(false);
    setErreur(null);
    setEtat("pret");
    setPhase("");
  };

  // --- Manuel : regrouper par couple et evaluer ---
  async function evaluer() {
    const assignes = affect.filter(
      (r) => r.id_vehicule !== "" && r.id_chauffeur !== ""
    );
    if (assignes.length === 0) {
      setErreur({ texte: "Affecte au moins un lot à un véhicule avant d'évaluer." });
      setEtat("erreur");
      return;
    }

    // Regroupement client : un couple (vehicule, chauffeur) distinct = une tournee.
    const groupes = new Map();
    for (const r of assignes) {
      const cle = `${r.id_vehicule}|${r.id_chauffeur}`;
      if (!groupes.has(cle)) {
        groupes.set(cle, {
          id_vehicule: r.id_vehicule,
          id_chauffeur: r.id_chauffeur,
          ids_lots: [],
        });
      }
      groupes.get(cle).ids_lots.push(r.id_lot);
    }
    const affectations = [...groupes.values()];

    setEtat("encours");
    setPhase("Évaluation…");
    setErreur(null);
    setEvaluation(null);

    const controleur = new AbortController();
    const minuteur = setTimeout(() => controleur.abort(), TIMEOUT_MS);

    try {
      const re = await fetch(`${API_URL}/evaluations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_vague: idVague, affectations }),
        signal: controleur.signal,
      });
      const corps = await re.json().catch(() => null);
      if (!re.ok) {
        setErreur(messageErreur(re.status, corps));
        setEtat("erreur");
        return;
      }
      setEvaluation(corps);
      setEvalPerimee(false);
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
  const nbAffectes = affect.filter((r) => r.id_vehicule !== "").length;

  return (
    <div style={pageStyle}>
      <div style={barreStyle}>
        <Link to="/" style={lienRetourStyle}>← Carte</Link>
        <span style={titreStyle}>
          {vue === "saisie" ? "Saisir des lots à livrer" : "Affectation manuelle"}
        </span>
      </div>

      <div style={corpsStyle}>
        {refErreur && (
          <p style={{ color: "#c62828" }}>
            Impossible de charger les référentiels : {refErreur}
          </p>
        )}

        {/* ============================ VUE SAISIE ============================ */}
        {vue === "saisie" && (
          <>
            <p style={introStyle}>
              Renseigne les lots d'une nouvelle vague. Les dépôts et destinations
              sont ceux de la base (listes déroulantes). « Optimiser » lance le
              solveur ; « Affectation manuelle » te laisse composer les tournées.
            </p>

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

            {/* Actions : auto (Phase 1) et manuel (Phase 2) */}
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
                onClick={preparerAffectation}
                disabled={occupe}
                style={occupe ? boutonOccupeStyle : boutonManuelStyle}
                title="Composer les tournées à la main puis évaluer"
              >
                Affectation manuelle
              </button>
            </div>

            {etat === "erreur" && erreur && <BlocErreur erreur={erreur} />}
            {etat === "ok" && resultat && <BlocResultat resultat={resultat} />}
          </>
        )}

        {/* ========================= VUE AFFECTATION ========================= */}
        {vue === "affectation" && (
          <>
            <p style={introStyle}>
              Vague <strong>{idVague}</strong> enregistrée ({affect.length} lots).
              Affecte chaque lot à un véhicule ; le chauffeur est celui du binôme,
              modifiable. Les lots laissés « non affecté » remonteront comme non
              livrés. L'évaluation contrôle les violations sans les bloquer et
              réordonne chaque tournée (TSP).
            </p>

            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>#</th>
                  <th style={thStyle}>Volume (m³)</th>
                  <th style={thStyle}>Caisson</th>
                  <th style={thStyle}>Dépôt</th>
                  <th style={thStyle}>Destination</th>
                  <th style={thStyle}>Véhicule</th>
                  <th style={thStyle}>Chauffeur</th>
                </tr>
              </thead>
              <tbody>
                {affect.map((r, i) => (
                  <tr key={r.id_lot}>
                    <td style={tdStyle}>{i + 1}</td>
                    <td style={tdStyle}>{r.volume}</td>
                    <td style={tdStyle}>{r.caisson_requis}</td>
                    <td style={tdStyle}>{nomStation(r.id_station_source)}</td>
                    <td style={tdStyle}>{nomDestination(r.id_destination)}</td>
                    <td style={tdStyle}>
                      <select
                        value={r.id_vehicule}
                        onChange={(e) => majAffectVehicule(i, e.target.value)}
                        style={selectStyle}
                        disabled={occupe}
                      >
                        <option value="">— non affecté —</option>
                        {vehiculesAffectables.map((v) => (
                          <option key={v.id_vehicule} value={v.id_vehicule}>
                            {libelleVehicule(v)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td style={tdStyle}>
                      <select
                        value={r.id_chauffeur}
                        onChange={(e) => majAffectChauffeur(i, e.target.value)}
                        style={selectStyle}
                        disabled={occupe || r.id_vehicule === ""}
                      >
                        {r.id_vehicule === "" ? (
                          <option value="">—</option>
                        ) : (
                          chauffeurs.map((c) => (
                            <option key={c.id_chauffeur} value={c.id_chauffeur}>
                              {c.nom}
                            </option>
                          ))
                        )}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={actionsStyle}>
              <button
                type="button"
                onClick={retourSaisie}
                style={boutonSecondaireStyle}
                disabled={occupe}
              >
                ← Retour saisie
              </button>
              <button
                type="button"
                onClick={evaluer}
                disabled={occupe || nbAffectes === 0}
                style={
                  occupe
                    ? boutonOccupeStyle
                    : nbAffectes === 0
                    ? boutonDesactiveStyle
                    : boutonPrincipalStyle
                }
              >
                {occupe
                  ? `${phase} ${secondes} s`
                  : `${evaluation ? "Ré-évaluer" : "Évaluer"} (${nbAffectes} affectés)`}
              </button>
            </div>

            {etat === "erreur" && erreur && <BlocErreur erreur={erreur} />}

            {etat === "ok" && evaluation && (
              <div style={{ marginTop: 24 }}>
                {evalPerimee && (
                  <div style={boitePerimeeStyle}>
                    Affectation modifiée depuis cette évaluation — les résultats
                    ci-dessous sont périmés. Clique « Ré-évaluer » pour les mettre à jour.
                  </div>
                )}

                <div style={evalPerimee ? { opacity: 0.45 } : undefined}>
                  <p style={succesStyle}>✓ Évaluation de la vague {idVague}.</p>

                  <div style={resumeStyle}>
                    <span><strong>{evaluation.nb_tournees}</strong> tournées</span>
                    <span><strong>{evaluation.distance_totale_km}</strong> km au total</span>
                    <span style={evaluation.nb_violations > 0 ? { color: "#c62828" } : undefined}>
                      <strong>{evaluation.nb_violations}</strong> violation(s)
                    </span>
                    <span>
                      <strong>{evaluation.lots_non_affectes.length}</strong> lot(s) non affecté(s)
                    </span>
                  </div>

                  {evaluation.lots_non_affectes.length > 0 && (
                    <p style={{ fontSize: 13, color: "#555", marginTop: 12 }}>
                      Lots non affectés : {evaluation.lots_non_affectes.join(", ")}
                    </p>
                  )}

                  <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
                    {evaluation.tournees.map((t, i) => {
                      // Impact des violations :
                      //  - capacite (id_lot null) = fait de tournee -> ligne charge/taux
                      //  - caisson / source (id_lot) -> arret concerne dans l'ordre
                      const violCapacite = t.violations.filter((v) => v.id_lot == null);
                      const surchargee = violCapacite.length > 0;
                      const violParLot = new Map();
                      t.violations.forEach((v) => {
                        if (v.id_lot != null) {
                          if (!violParLot.has(v.id_lot)) violParLot.set(v.id_lot, []);
                          violParLot.get(v.id_lot).push(v);
                        }
                      });

                      return (
                        <div key={i} style={carteTourneeStyle}>
                          <div style={{ fontWeight: "bold", marginBottom: 6 }}>
                            V{t.id_vehicule} · {nomChauffeur(t.id_chauffeur)} · départ {nomStation(t.id_station_depart)}
                          </div>

                          {/* Metriques : taux en rouge si surcharge, message d'impact juste dessous */}
                          <div style={{ fontSize: 13, color: "#444", marginBottom: surchargee ? 2 : 6 }}>
                            {t.distance_km} km · charge{" "}
                            <span style={surchargee ? metriqueFauteStyle : undefined}>
                              {t.charge_m3}/{t.capacite_m3} m³ · {t.taux_charge} %
                            </span>
                          </div>
                          {violCapacite.map((v, k) => (
                            <div key={k} style={ligneViolationStyle}>⚠ {v.message}</div>
                          ))}

                          {/* Ordre : chaque arret fautif en rouge, avec son ou ses badges */}
                          <div style={{ fontSize: 13, marginTop: 6, lineHeight: 1.9 }}>
                            <span style={{ color: "#666" }}>Ordre : </span>
                            {t.ordre_lots.map((idLot, k) => {
                              const vs = violParLot.get(idLot) ?? [];
                              const enFaute = vs.length > 0;
                              const nom = nomDestination(destinationDuLot(idLot));
                              return (
                                <span key={idLot}>
                                  <span
                                    style={enFaute ? arretFauteStyle : undefined}
                                    title={enFaute ? vs.map((v) => v.message).join(" | ") : undefined}
                                  >
                                    {nom}
                                    {vs.map((v, j) => (
                                      <span key={j} style={badgeViolationStyle}>{v.type}</span>
                                    ))}
                                  </span>
                                  {k < t.ordre_lots.length - 1 && (
                                    <span style={{ color: "#999" }}> → </span>
                                  )}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
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
  // 422 / 500 : detail = chaine (ex. evaluation : vehicule ou lot introuvable)
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

// Libelle d'un lot non servi. l'API renvoie des OBJETS
// ({id_lot, nom_destination, id_destination, raison}), plus des identifiants
// nus : un .join() direct produisait "[object Object]". On formate ici, avec
// des replis defensifs (meme logique que RunDetail.formaterDestinationLot) :
//   - objet complet  -> "Lot 45 — Nabeul (12)"
//   - objet partiel  -> "Lot 45"
//   - identifiant nu  -> "45"
// Le detail complet (destination + raison lisible) reste un clic plus loin,
// via "Voir le detail ->".
function libelleLotNonServi(l) {
  if (typeof l !== "object" || l === null) return String(l);
  const dest = l.nom_destination
    ? `${l.nom_destination}${l.id_destination != null ? ` (${l.id_destination})` : ""}`
    : null;
  return dest ? `Lot ${l.id_lot} — ${dest}` : `Lot ${l.id_lot}`;
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
          Lots non servis : {lots_non_servis.map(libelleLotNonServi).join(", ")}
        </p>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
        <Link to={`/runs/${id_run}`} style={lienDetailStyle}>Voir le détail →</Link>
        <Link to={`/kpis?run=${id_run}`} style={lienKpisStyle}>Tableau de bord →</Link>
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
const boutonManuelStyle = {
  background: "#1565c0",
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
const carteTourneeStyle = {
  padding: "10px 14px",
  background: "#fafafa",
  border: "1px solid #e0e0e0",
  borderRadius: 8,
};
const metriqueFauteStyle = { color: "#c62828", fontWeight: "bold" };
const ligneViolationStyle = { fontSize: 12, color: "#c62828", marginBottom: 2 };
const arretFauteStyle = {
  color: "#c62828",
  fontWeight: "bold",
  background: "#fdecea",
  borderRadius: 4,
  padding: "1px 5px",
};
const badgeViolationStyle = {
  marginLeft: 4,
  fontSize: 10,
  fontWeight: "bold",
  color: "white",
  background: "#c62828",
  borderRadius: 3,
  padding: "0 4px",
  textTransform: "uppercase",
  letterSpacing: 0.3,
  verticalAlign: "middle",
};
const boitePerimeeStyle = {
  marginBottom: 12,
  padding: "8px 12px",
  background: "#fff8e1",
  border: "1px solid #ffe082",
  borderRadius: 8,
  fontSize: 13,
  color: "#5f4b00",
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
// Rebond "Tableau de bord" : bleu en contour, meme famille que dans CarteView
// (consultation du run courant), distinct du "Detail" bleu plein.
const lienKpisStyle = {
  textDecoration: "none",
  background: "white",
  color: "#1565c0",
  border: "1px solid #90caf9",
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