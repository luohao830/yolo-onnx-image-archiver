import { Boxes, Cpu, Home, LogOut, Sliders } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { cn } from "../../lib/utils";

interface AdminSidebarProps {
  onLogout: () => void;
}

const NAV = [
  { to: "/admin/models", label: "模型管理", icon: Boxes },
  { to: "/admin/configs", label: "系统配置", icon: Sliders },
  { to: "/admin/jobs", label: "任务监控", icon: Cpu },
];

/** 管理员后台侧边栏：可折叠导航 + 登出。 */
export function AdminSidebar({ onLogout }: AdminSidebarProps) {
  const { pathname } = useLocation();
  return (
    <aside className="flex h-screen w-56 flex-none flex-col border-r border-line bg-card">
      <div className="flex items-center gap-2 px-4 py-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand text-white">
          <Sliders className="h-4 w-4" aria-hidden />
        </span>
        <span className="text-sm font-bold text-ink">管理后台</span>
      </div>
      <nav aria-label="后台导航" className="flex flex-1 flex-col gap-1 px-2">
        {NAV.map(({ to, label, icon: Icon }) => {
          const active = pathname === to || pathname.startsWith(`${to}/`);
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? "page" : undefined}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-bold transition-colors",
                active ? "bg-brand text-white" : "text-muted hover:bg-slate-100 hover:text-ink",
              )}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </Link>
          );
        })}
        <Link
          to="/"
          className="mt-auto inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-bold text-muted transition-colors hover:bg-slate-100 hover:text-ink"
        >
          <Home className="h-4 w-4" aria-hidden />
          返回前台
        </Link>
      </nav>
      <div className="border-t border-line p-2">
        <button
          type="button"
          onClick={onLogout}
          className="inline-flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-bold text-muted transition-colors hover:bg-red-50 hover:text-red-700"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          登出
        </button>
      </div>
    </aside>
  );
}
