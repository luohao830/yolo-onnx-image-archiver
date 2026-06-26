import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-line-strong bg-page/60 px-6 py-12 text-center",
        className,
      )}
    >
      {Icon ? (
        <Icon className="h-10 w-10 text-slate-400" aria-hidden />
      ) : (
        <span className="h-10 w-10 rounded-full bg-slate-200" aria-hidden />
      )}
      <div className="space-y-1">
        <p className="text-base font-bold text-ink">{title}</p>
        {description ? <p className="text-sm leading-relaxed text-muted">{description}</p> : null}
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
