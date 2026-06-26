import { ChevronDown, ScrollText } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "../../lib/utils";
import type { JobEvent } from "../../api/client";
import { Badge } from "../ui/badge";

const EVENT_VARIANT: Record<string, "running" | "completed" | "failed" | "neutral" | "uploaded"> = {
  running: "running",
  uploaded: "uploaded",
  completed: "completed",
  failed: "failed",
  canceled: "neutral",
};

interface LogPanelProps {
  events: JobEvent[];
  className?: string;
}

/** 深色日志面板：时间戳等宽 + 级别 Badge + 消息，自动滚动 + 手动上滚暂停。 */
export function LogPanel({ events, className }: LogPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (!autoScroll) return;
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events, autoScroll]);

  function handleScroll() {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  }

  return (
    <section
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-line bg-log p-4 text-slate-100 shadow-[0_14px_34px_rgba(15,23,42,0.06)]",
        className,
      )}
      aria-label="任务日志"
    >
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-slate-200">
          <ScrollText className="h-4 w-4 text-sky-300" aria-hidden />
          运行日志
        </h2>
        {!autoScroll ? (
          <button
            type="button"
            onClick={() => setAutoScroll(true)}
            className="inline-flex items-center gap-1 rounded-md bg-sky-500/20 px-2 py-1 text-xs font-bold text-sky-200 hover:bg-sky-500/30"
          >
            <ChevronDown className="h-3.5 w-3.5" aria-hidden />
            新日志
          </button>
        ) : null}
      </div>

      {events.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-400">暂无日志</p>
      ) : (
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="scrollbar-dark max-h-72 overflow-auto pr-1"
        >
          <ul className="flex flex-col gap-1">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex items-start gap-3 border-b border-slate-700/40 py-2 last:border-b-0"
              >
                <span className="mt-0.5 inline-flex flex-none">
                  <Badge variant={EVENT_VARIANT[event.event_type] ?? "neutral"} className="text-[10px]">
                    {event.event_type}
                  </Badge>
                </span>
                <p className="m-0 flex-1 text-sm leading-relaxed text-slate-200">
                  {event.message}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
