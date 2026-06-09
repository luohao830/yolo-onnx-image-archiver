import { Route, Routes } from "react-router-dom";

import { AdvancedModePage } from "./pages/AdvancedModePage";
import { HomePage } from "./pages/HomePage";
import { LookupPage } from "./pages/LookupPage";
import { PersonFilterPage } from "./pages/PersonFilterPage";
import { ResultPage } from "./pages/ResultPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/person-filter" element={<PersonFilterPage />} />
      <Route path="/advanced" element={<AdvancedModePage />} />
      <Route path="/lookup" element={<LookupPage />} />
      <Route path="/results/:jobCode" element={<ResultPage />} />
    </Routes>
  );
}
