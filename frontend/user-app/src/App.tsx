import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AdminSidebar } from "./components/layout/AdminSidebar";
import { AdvancedModePage } from "./pages/AdvancedModePage";
import { HomePage } from "./pages/HomePage";
import { PersonFilterPage } from "./pages/PersonFilterPage";
import { ResultPage } from "./pages/ResultPage";
import { ConfigsPage } from "./pages/admin/ConfigsPage";
import { JobsPage } from "./pages/admin/JobsPage";
import { LoginPage } from "./pages/admin/LoginPage";
import { ModelsPage } from "./pages/admin/ModelsPage";

const ADMIN_TOKEN_KEY = "admin-token";
const ADMIN_AUTO_LOGIN_DISABLED_KEY = "admin-auto-login-disabled";

interface AdminLayoutProps {
  onLogout: () => void;
}

function AdminLayout({ onLogout }: AdminLayoutProps) {
  return (
    <div className="flex min-h-screen bg-page">
      <AdminSidebar onLogout={onLogout} />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="models" element={<ModelsPage />} />
          <Route path="configs" element={<ConfigsPage />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="*" element={<Navigate to="/admin/configs" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  const [adminToken, setAdminToken] = useState(() => localStorage.getItem(ADMIN_TOKEN_KEY) ?? "");

  function handleAdminLogout() {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.setItem(ADMIN_AUTO_LOGIN_DISABLED_KEY, "1");
    setAdminToken("");
  }

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/person-filter" element={<PersonFilterPage />} />
      <Route path="/advanced" element={<AdvancedModePage />} />
      <Route path="/results/:jobCode" element={<ResultPage />} />
      <Route
        path="/admin/*"
        element={adminToken ? <AdminLayout onLogout={handleAdminLogout} /> : <LoginPage onLogin={setAdminToken} />}
      />
      <Route path="/lookup" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
