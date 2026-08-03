import { BrowserRouter, Routes, Route } from "react-router-dom";
import CarteView from "./CarteView";
import RunDetail from "./RunDetail";
import LancerOptim from "./LancerOptim";
import SaisieLots from "./SaisieLots";
import TableauDeBord from "./TableauDeBord";

// Coquille de routage : chaque ecran est un composant sur sa route.
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CarteView />} />
        <Route path="/saisie" element={<SaisieLots />} />
        <Route path="/lancer" element={<LancerOptim />} />
        <Route path="/kpis" element={<TableauDeBord />} />
        <Route path="/runs/:idRun" element={<RunDetail />} />
      </Routes>
    </BrowserRouter>
  );
}