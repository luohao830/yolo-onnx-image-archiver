import { Navigate, Route, Routes } from "react-router-dom";

import { AdvancedModePage } from "./pages/AdvancedModePage";
import { HomePage } from "./pages/HomePage";
import { PersonFilterPage } from "./pages/PersonFilterPage";
import { ResultPage } from "./pages/ResultPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/person-filter" element={<PersonFilterPage />} />
      <Route path="/advanced" element={<AdvancedModePage />} />
      <Route path="/results/:jobCode" element={<ResultPage />} />
      <Route path="/lookup" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
