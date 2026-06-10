import { useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { ConfigsPage } from "./pages/ConfigsPage";
import { LoginPage } from "./pages/LoginPage";
import { JobsPage } from "./pages/JobsPage";
import { ModelsPage } from "./pages/ModelsPage";
import { UploadedArchivesPage } from "./pages/UploadedArchivesPage";

const ADMIN_TOKEN_KEY = "admin-token";
const ADMIN_AUTO_LOGIN_DISABLED_KEY = "admin-auto-login-disabled";

interface AdminLayoutProps {
  onLogout: () => void;
}

function AdminLayout({ onLogout }: AdminLayoutProps) {
  return (
    <main>
      <nav aria-label="后台导航">
        <Link to="/models">模型管理</Link>
        <Link to="/configs">系统配置</Link>
        <Link to="/jobs">任务监控</Link>
        <Link to="/uploads">压缩包管理</Link>
        <button className="nav-logout" type="button" onClick={onLogout}>
          登出
        </button>
      </nav>
      <Routes>
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/configs" element={<ConfigsPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/uploads" element={<UploadedArchivesPage />} />
        <Route path="*" element={<Navigate to="/models" replace />} />
      </Routes>
    </main>
  );
}

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem(ADMIN_TOKEN_KEY) ?? "");

  function handleLogout() {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.setItem(ADMIN_AUTO_LOGIN_DISABLED_KEY, "1");
    setToken("");
  }

  if (!token) {
    return <LoginPage onLogin={setToken} />;
  }

  return <AdminLayout onLogout={handleLogout} />;
}
