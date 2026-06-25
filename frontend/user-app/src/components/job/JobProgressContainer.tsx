import { Clock, Cpu, Image as ImageIcon, PackageCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";

import {
  buildJobDownloadUrl,
  getJobStatus,
  subscribeJobEvents,
  type PublicJobStatus,
} from "../../api/client";
import type { JobStats, JobStatus } from "../../api/types";
import { useJobLiveStatus } from "../../hooks/useJobLiveStatus";
import { clampProgress, cn, formatSeconds, getFallbackProgress, isTerminalStatus } from "../../lib/utils";
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

/** 组合进度时间线、KPI 行、深色日志面板；SSE 订阅 + 降级轮询。 */
export function JobProgressContainer({
  jobCode,
  accessToken,
  initialStatus = "created",
  className,
  onStatus,
}: JobProgressContainerProps) {
  const normalizedJobCode = useMemo(() => jobCode.trim(), [jobCode]);
  const normalizedAccessToken = useMemo(() => accessToken.trim(), [accessToken]);
  const enabled = Boolean(normalizedJobCode && normalizedAccessToken);
  const onStatusRef = useRef(onStatus);
  onStatusRef.current = onStatus;

  const fetchSnapshot = useCallback(async () => {
    if (!normalizedJobCode || !normalizedAccessToken) {
      throw new Error("任务状态不可用，请重新提交任务。");
    }
    return getJobStatus(normalizedJobCode, normalizedAccessToken);
  }, [normalizedJobCode, normalizedAccessToken]);

  const subscribe = useCallback(
    (onEvent: () => void, onError: (error: Event | Error) => void) => {
      if (!normalizedJobCode || !normalizedAccessToken) return () => {};
      return subscribeJobEvents(normalizedJobCode, normalizedAccessToken, onEvent, onError);
    },
    [normalizedJobCode, normalizedAccessToken],
  );

  const isTerminal = useCallback(
    (snapshot: PublicJobStatus) => isTerminalStatus(snapshot.status),
    [],
  );

  const {
    snapshot: result,
    errorMessage,
    realtimeFailed,
  } = useJobLiveStatus<PublicJobStatus>({
    enabled,
    fetchSnapshot,
    subscribe,
    isTerminal,
    pollIntervalMs: POLL_INTERVAL_MS,
  });

  useEffect(() => {
    if (result) onStatusRef.current?.(result);
  }, [result]);

  const status = result?.status ?? initialStatus;
  const progress = clampProgress(result?.progress ?? getFallbackProgress(status));
  const events = result?.events ?? [];
  const summary: JobStats | null = result?.summary ?? null;
  const downloadUrl =
    result?.download_ready && status === "completed"
      ? buildJobDownloadUrl(normalizedJobCode, normalizedAccessToken)
      : "";

  const totalImages: number | undefined = summary?.total;
  const written: number | undefined = summary?.written;
  const elapsed = summary?.elapsed_sec;
  const gpu = summary?.cuda_enabled ? "CUDA" : "CPU";
  const displayError = enabled ? errorMessage : "任务状态不可用，请重新提交任务。";

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
              {realtimeFailed ? "实时推送中断，已降级轮询" : "最新状态已同步"}
            </span>
          </div>
        </div>
        <Progress value={progress} active={status === "running"} />
        <ProgressTimeline status={status} events={events} />

        {displayError ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{displayError}</p> : null}
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
