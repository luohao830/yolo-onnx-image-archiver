import { ArrowDownRight, ArrowUpRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";
import { Card } from "../ui/card";

interface KpiCardProps {
  title: string;
  value: ReactNode;
  icon?: LucideIcon;
  hint?: ReactNode;
  /** 趋势：up/down/none */
  trend?: "up" | "down" | "none";
  className?: string;
}

/** Tremor 风格 KPI 卡片：标题 + 数值 + 趋势箭头。 */
export function KpiCard({ title, value, icon: Icon, hint, trend = "none", className }: KpiCardProps) {
  return (
    <Card className={cn("flex flex-col gap-2 p-4", className)}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-wide text-subtle">{title}</p>
        {Icon ? <Icon className="h-4 w-4 text-slate-400" aria-hidden /> : null}
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold leading-none text-ink">{value}</span>
        {trend === "up" ? (
          <ArrowUpRight className="mb-0.5 h-4 w-4 text-green-600" aria-hidden />
        ) : null}
        {trend === "down" ? (
          <ArrowDownRight className="mb-0.5 h-4 w-4 text-red-600" aria-hidden />
        ) : null}
      </div>
      {hint ? <p className="text-xs leading-relaxed text-muted">{hint}</p> : null}
    </Card>
  );
}
