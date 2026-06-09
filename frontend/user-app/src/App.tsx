import { Route, Routes } from "react-router-dom";

import { HomePage } from "./pages/HomePage";
import { PersonFilterPage } from "./pages/PersonFilterPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/person-filter" element={<PersonFilterPage />} />
      <Route
        path="/advanced"
        element={
          <main>
            <h1>高级模式</h1>
            <p>高级模式页面将在后续任务中接入。</p>
          </main>
        }
      />
    </Routes>
  );
}
