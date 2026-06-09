import { useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { ConfigsPage } from "./pages/ConfigsPage";
import { LoginPage } from "./pages/LoginPage";
import { JobsPage } from "./pages/JobsPage";
import { ModelsPage } from "./pages/ModelsPage";

const ADMIN_TOKEN_KEY = "admin-token";

function AdminLayout() {
  return (
    <main>
      <nav aria-label="后台导航">
        <Link to="/models">模型管理</Link>
        <Link to="/configs">系统配置</Link>
        <Link to="/jobs">任务监控</Link>
      </nav>
      <Routes>
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/configs" element={<ConfigsPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="*" element={<Navigate to="/models" replace />} />
      </Routes>
    </main>
  );
}

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem(ADMIN_TOKEN_KEY) ?? "");

  if (!token) {
    return <LoginPage onLogin={setToken} />;
  }

  return <AdminLayout />;
}
