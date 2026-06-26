import { Check } from "lucide-react";

import { cn } from "../../lib/utils";
import type { JobEvent, JobStatus } from "../../api/client";

const STAGES: Array<{ key: JobStatus; label: string }> = [
  { key: "created", label: "创建任务" },
  { key: "uploaded", label: "上传入队" },
  { key: "running", label: "推理执行" },
  { key: "completed", label: "完成" },
];

const ORDER: JobStatus[] = STAGES.map((s) => s.key);

function stageTimestamp(status: JobStatus, events: JobEvent[]): string | null {
  const event = events.find((e) => e.event_type === status);
  if (!event) return null;
  const ts = event.payload_json?.timestamp;
  return typeof ts === "string" ? ts : null;
}

interface ProgressTimelineProps {
  status: JobStatus;
  events: JobEvent[];
  className?: string;
}

/** 进度时间线：created→uploaded→running→completed 四节点。 */
export function ProgressTimeline({ status, events, className }: ProgressTimelineProps) {
  const currentIndex = ORDER.indexOf(status);
  // failed/canceled 不在 ORDER 中（indexOf 返回 -1），此时停在 running 阶段。
  const reachableIndex =
    status === "failed" || status === "canceled"
      ? ORDER.indexOf("running")
      : currentIndex;

  return (
    <ol className={cn("flex flex-col gap-3", className)}>
      {STAGES.map((stage, idx) => {
        const done = idx < reachableIndex || (idx === reachableIndex && (status === "completed"));
        const current = idx === reachableIndex && status !== "completed";
        const ts = stageTimestamp(stage.key, events);
        return (
          <li key={stage.key} className="flex items-start gap-3">
            <span
              className={cn(
                "mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full border text-xs font-bold transition-colors",
                done && "border-brand bg-brand text-white",
                current && "border-brand bg-brand/10 text-brand",
                !done && !current && "border-line-strong bg-card text-slate-400",
                current && "ring-4 ring-brand/20",
              )}
              aria-current={current ? "step" : undefined}
            >
              {done ? <Check className="h-3.5 w-3.5" aria-hidden /> : idx + 1}
            </span>
            <div className="flex flex-col">
              <span
                className={cn(
                  "text-sm font-bold",
                  done || current ? "text-ink" : "text-slate-400",
                )}
              >
                {stage.label}
              </span>
              {ts ? (
                <span className="font-mono text-xs text-subtle">{ts}</span>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
