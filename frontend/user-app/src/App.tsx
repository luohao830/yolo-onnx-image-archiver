import { useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

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
    <main className="admin-shell">
      <nav aria-label="后台导航">
        <Link to="/">返回上传页</Link>
        <Link to="/admin/models">模型管理</Link>
        <Link to="/admin/configs">系统配置</Link>
        <Link to="/admin/jobs">任务监控</Link>
        <button className="nav-logout" type="button" onClick={onLogout}>
          登出
        </button>
      </nav>
      <Routes>
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/configs" element={<ConfigsPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="*" element={<Navigate to="/admin/configs" replace />} />
      </Routes>
    </main>
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
