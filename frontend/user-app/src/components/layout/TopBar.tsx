import { Layers, ScanSearch, Settings2 } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { cn } from "../../lib/utils";

interface TopBarProps {
  /** 右侧附加操作（如管理员入口/查找入口） */
  extra?: React.ReactNode;
}

/** 用户前台窄条顶栏：Logo + 模式切换 + 右侧入口。 */
export function TopBar({ extra }: TopBarProps) {
  const { pathname } = useLocation();
  const tabs = [
    { to: "/person-filter", label: "人员筛选", icon: ScanSearch },
    { to: "/advanced", label: "高级模式", icon: Layers },
  ];

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-card/90 backdrop-blur">
      <div className="mx-auto flex w-[min(1120px,calc(100%-32px))] items-center justify-between gap-4 py-3">
        <Link to="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand text-white">
            <Settings2 className="h-4 w-4" aria-hidden />
          </span>
          <span className="text-sm font-bold tracking-tight text-ink">YOLO 推理平台</span>
        </Link>

        <nav aria-label="模式切换" className="flex items-center gap-1 rounded-lg border border-line bg-card p-1">
          {tabs.map(({ to, label, icon: Icon }) => {
            const active = pathname === to;
            return (
              <Link
                key={to}
                to={to}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-flex min-h-9 items-center gap-1.5 rounded-md px-3 text-sm font-bold transition-colors",
                  active ? "bg-brand text-white" : "text-muted hover:bg-slate-100 hover:text-ink",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden />
                {label}
              </Link>
            );
          })}
        </nav>

        {extra ? <div className="flex items-center gap-2">{extra}</div> : null}
      </div>
    </header>
  );
}
