import { Link, Route, Routes } from "react-router-dom";

export function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <main>
            <h1>图片任务平台</h1>
            <Link to="/person-filter">人员筛选模式</Link>
            <Link to="/advanced">高级模式</Link>
          </main>
        }
      />
    </Routes>
  );
}
