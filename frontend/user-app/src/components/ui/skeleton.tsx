import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "../../lib/utils";

export const Skeleton = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("animate-pulse rounded-md bg-slate-200/80", className)}
      {...props}
    />
  ),
);
Skeleton.displayName = "Skeleton";
