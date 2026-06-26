import { cn } from "../../lib/utils";
import { Badge } from "../ui/badge";
import type { JobStatus } from "../../api/client";

const STATUS_LABELS: Record<JobStatus, string> = {
  created: "待上传",
  uploaded: "已入队",
  running: "推理中",
  completed: "已完成",
  failed: "已失败",
  canceled: "已取消",
};

interface StatusBadgeProps {
  status: JobStatus;
  className?: string;
}

/** 状态徽章：颜色 + 文字双重编码（DESIGN.md）。 */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge variant={status} className={cn("transition-colors duration-200", className)}>
      <span
        className={cn(
          "mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-current",
          status === "running" && "animate-pulse",
        )}
        aria-hidden
      />
      {STATUS_LABELS[status] ?? status}
      <span className="sr-only">{status}</span>
    </Badge>
  );
}

export { STATUS_LABELS };
