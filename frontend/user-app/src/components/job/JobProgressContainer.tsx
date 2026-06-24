import { Clock, Cpu, Image as ImageIcon, PackageCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  buildJobDownloadUrl,
  getJobStatus,
  subscribeJobEvents,
  type JobEvent,
  type JobStats,
  type JobStatus,
  type PublicJobStatus,
} from "../../api/client";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";
import { Progress } from "../ui/progress";
import { KpiCard } from "./KpiCard";
import { LogPanel } from "./LogPanel";
import { ProgressTimeline } from "./ProgressTimeline";
import { StatusBadge } from "./StatusBadge";

const POLL_INTERVAL_MS = 2000;

interface JobProgressContainerProps {
  jobCode: string;
  accessToken: string;
  initialStatus?: JobStatus;
  className?: string;
  /** 状态变更回调，供外层加载结果可视化等。 */
  onStatus?: (status: PublicJobStatus) => void;
}

function isTerminalStatus(status: JobStatus): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}

function getFallbackProgress(status: JobStatus): number {
  const values: Record<JobStatus, number> = {
    created: 0,
    uploaded: 100,
    running: 0,
    completed: 100,
    failed: 100,
    canceled: 0,
  };
  return values[status];
}

function clampProgress(progress: number): number {
  return Math.max(0, Math.min(100, Math.round(progress)));
}

function formatSeconds(value?: number): string {
  if (value === undefined || value === null) return "—";
  if (value < 1) return `${(value * 1000).toFixed(0)} ms`;
  return `${value.toFixed(2)} s`;
}

/** 组合进度时间线、KPI 行、深色日志面板；SSE 订阅 + 降级轮询。 */
export function JobProgressContainer({
  jobCode,
  accessToken,
  initialStatus = "created",
  className,
  onStatus,
}: JobProgressContainerProps) {
  const [result, setResult] = useState<PublicJobStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [sseFailed, setSseFailed] = useState(false);
  const [pollTick, setPollTick] = useState(0);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);
  const onStatusRef = useRef(onStatus);
  onStatusRef.current = onStatus;

  const fetchStatus = useCallback(async () => {
    if (!jobCode.trim() || !accessToken.trim()) {
      setErrorMessage("任务状态不可用，请重新提交任务。");
      return;
    }
    try {
      const next = await getJobStatus(jobCode.trim(), accessToken.trim());
      if (stoppedRef.current) return;
      setResult(next);
      setErrorMessage(null);
      onStatusRef.current?.(next);
    } catch (error) {
      if (stoppedRef.current) return;
      setErrorMessage(error instanceof Error ? error.message : "获取任务状态失败");
    } finally {
      if (!stoppedRef.current) setPollTick((t) => t + 1);
    }
  }, [jobCode, accessToken]);

  // SSE 订阅：收到事件后触发一次状态轮询同步进度与终态；失败则降级轮询。
  useEffect(() => {
    if (!jobCode.trim() || !accessToken.trim()) return;
    stoppedRef.current = false;
    setSseFailed(false);

    void fetchStatus();

    let unsubscribe: (() => void) | null = null;
    try {
      unsubscribe = subscribeJobEvents(
        jobCode.trim(),
        accessToken.trim(),
        () => {
          if (stoppedRef.current) return;
          void fetchStatus();
        },
        () => {
          if (stoppedRef.current) return;
          setSseFailed(true);
        },
      );
    } catch {
      // SSE 不可用（如测试环境或浏览器不支持）时降级为轮询。
      setSseFailed(true);
    }

    return () => {
      stoppedRef.current = true;
      try {
        unsubscribe?.();
      } catch {
        // ignore
      }
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [jobCode, accessToken, fetchStatus]);

  // 降级轮询：SSE 不可用或终态前定时拉取（每次 fetchStatus 完成后通过 pollTick 重新调度）。
  useEffect(() => {
    const status = result?.status ?? initialStatus;
    if (isTerminalStatus(status)) return;
    pollTimerRef.current = setTimeout(() => {
      void fetchStatus();
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [result, sseFailed, initialStatus, fetchStatus, pollTick]);

  const status = result?.status ?? initialStatus;
  const progress = clampProgress(result?.progress ?? getFallbackProgress(status));
  const events = result?.events ?? [];
  const summary: JobStats | null = result?.summary ?? null;
  const downloadUrl =
    result?.download_ready && status === "completed"
      ? buildJobDownloadUrl(jobCode, accessToken)
      : "";

  const totalImages: number | undefined = summary?.total;
  const written: number | undefined = summary?.written;
  const elapsed = summary?.elapsed_sec;
  const gpu = summary?.cuda_enabled ? "CUDA" : "CPU";

  return (
    <section className={cn("flex flex-col gap-5", className)} aria-label="任务处理状态">
      <div className="flex flex-col gap-4 rounded-lg border border-line bg-card p-5 shadow-[0_14px_34px_rgba(15,23,42,0.06)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <p className="text-xs font-bold uppercase tracking-wide text-brand">处理状态</p>
            <h2 className="text-xl font-bold text-ink">
              <StatusBadge status={status} />
            </h2>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className="text-3xl font-bold leading-none text-ink">{progress}%</span>
            <span className="text-xs text-subtle">
              {sseFailed ? "实时推送中断，已降级轮询" : "最新状态已同步"}
            </span>
          </div>
        </div>
        <Progress value={progress} active={status === "running"} />
        <ProgressTimeline status={status} events={events} />

        {errorMessage ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{errorMessage}</p> : null}
        {status === "failed" && result?.error_message ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{result.error_message}</p>
        ) : null}
        {status === "canceled" ? <p className="text-sm text-muted">任务已取消</p> : null}
      </div>

      {status === "completed" && summary ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <KpiCard title="总图数" value={totalImages ?? "—"} icon={ImageIcon} />
          <KpiCard title="已写入" value={written ?? "—"} icon={PackageCheck} trend={written && totalImages && written >= totalImages ? "up" : "none"} hint={totalImages ? `${written ?? 0} / ${totalImages}` : undefined} />
          <KpiCard title="总耗时" value={formatSeconds(elapsed)} icon={Clock} />
          <KpiCard title="推理设备" value={gpu} icon={Cpu} hint={summary.providers?.join(", ")} />
        </div>
      ) : null}

      <LogPanel events={events} />

      {downloadUrl ? (
        <a
          href={downloadUrl}
          className="inline-flex min-h-11 items-center justify-center gap-2 self-start rounded-md bg-green-600 px-5 text-base font-bold text-white transition-colors hover:bg-green-700"
        >
          下载结果压缩包
        </a>
      ) : null}
    </section>
  );
}
