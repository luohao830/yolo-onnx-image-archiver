import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold leading-none",
  {
    variants: {
      variant: {
        created: "bg-status-created-bg text-status-created-fg",
        uploaded: "bg-status-uploaded-bg text-status-uploaded-fg",
        running: "bg-status-running-bg text-status-running-fg",
        completed: "bg-status-completed-bg text-status-completed-fg",
        failed: "bg-status-failed-bg text-status-failed-fg",
        canceled: "bg-status-canceled-bg text-status-canceled-fg",
        neutral: "bg-slate-100 text-slate-600",
        brand: "bg-brand/10 text-brand",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
