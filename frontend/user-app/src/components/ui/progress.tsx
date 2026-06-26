import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "../../lib/utils";

interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  /** 0-100 */
  value: number;
  /** 是否处于活跃状态（运行中显示主色脉冲感） */
  active?: boolean;
}

/** 自建进度条：div + CSS width transition，不引 radix。 */
export const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, active = false, ...props }, ref) => {
    const clamped = Math.max(0, Math.min(100, value));
    return (
      <div
        ref={ref}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clamped)}
        className={cn(
          "h-3 w-full overflow-hidden rounded-full bg-line",
          className,
        )}
        {...props}
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-220 ease-out",
            active ? "bg-brand animate-pulse" : "bg-brand",
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
    );
  },
);
Progress.displayName = "Progress";
