import { Link, Navigate, Route, Routes } from "react-router-dom";

import { AdvancedModePage } from "./pages/AdvancedModePage";
import { HomePage } from "./pages/HomePage";
import { PersonFilterPage } from "./pages/PersonFilterPage";
import { ResultPage } from "./pages/ResultPage";
import { ConfigsPage } from "./pages/admin/ConfigsPage";
import { JobsPage } from "./pages/admin/JobsPage";
import { ModelsPage } from "./pages/admin/ModelsPage";

function AdminLayout() {
  return (
    <main className="admin-shell">
      <nav aria-label="后台导航">
        <Link to="/">返回上传页</Link>
        <Link to="/admin/models">模型管理</Link>
        <Link to="/admin/configs">系统配置</Link>
        <Link to="/admin/jobs">任务监控</Link>
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
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/person-filter" element={<PersonFilterPage />} />
      <Route path="/advanced" element={<AdvancedModePage />} />
      <Route path="/results/:jobCode" element={<ResultPage />} />
      <Route path="/admin/*" element={<AdminLayout />} />
      <Route path="/lookup" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
