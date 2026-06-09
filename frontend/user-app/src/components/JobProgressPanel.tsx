import { useEffect, useState } from "react";

import {
  buildJobDownloadUrl,
  getJobStatus,
  type JobStatus,
  type PublicJobStatus
} from "../api/client";

const POLL_INTERVAL_MS = 2000;

interface JobProgressPanelProps {
  jobCode: string;
  accessToken: string;
  initialStatus?: JobStatus;
}

function isTerminalStatus(status: JobStatus): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}

function getStatusLabel(status: JobStatus): string {
  const labels: Record<JobStatus, string> = {
    created: "任务已创建",
    uploaded: "文件已接收",
    running: "正在处理",
    completed: "处理完成",
    failed: "处理失败",
    canceled: "任务已取消"
  };

  return labels[status];
}

function clampProgress(progress: number): number {
  return Math.max(0, Math.min(100, Math.round(progress)));
}

export function JobProgressPanel({ jobCode, accessToken, initialStatus = "created" }: JobProgressPanelProps) {
  const [result, setResult] = useState<PublicJobStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!jobCode.trim() || !accessToken.trim()) {
      setResult(null);
      setErrorMessage("任务状态不可用，请重新提交任务。");
      return;
    }

    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    function scheduleNextPoll() {
      timer = setTimeout(() => {
        void pollStatus();
      }, POLL_INTERVAL_MS);
    }

    async function pollStatus() {
      setIsLoading(true);

      try {
        const nextStatus = await getJobStatus(jobCode.trim(), accessToken.trim());

        if (stopped) {
          return;
        }

        setResult(nextStatus);
        setErrorMessage(null);

        if (!isTerminalStatus(nextStatus.status)) {
          scheduleNextPoll();
        }
      } catch (error) {
        if (stopped) {
          return;
        }

        setErrorMessage(error instanceof Error ? error.message : "获取任务状态失败");
        scheduleNextPoll();
      } finally {
        if (!stopped) {
          setIsLoading(false);
        }
      }
    }

    void pollStatus();

    return () => {
      stopped = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [accessToken, jobCode]);

  const status = result?.status ?? initialStatus;
  const progress = clampProgress(result?.progress ?? 5);
  const events = result?.events ?? [];
  const downloadUrl =
    result?.download_ready && result.status === "completed"
      ? buildJobDownloadUrl(jobCode, accessToken)
      : "";

  return (
    <section className="task-console" aria-label="任务处理状态">
      <div className="status-panel">
        <div className="status-panel__header">
          <div>
            <p className="eyebrow">处理状态</p>
            <h2>{getStatusLabel(status)}</h2>
          </div>
          <span className={`status-badge status-badge--${status}`}>{status}</span>
        </div>

        <div className="progress-summary">
          <strong>{progress}%</strong>
          <span>{isLoading ? "正在刷新状态" : "最新状态已同步"}</span>
        </div>
        <div
          className="progress-track"
          role="progressbar"
          aria-label="任务处理进度"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <span style={{ width: `${progress}%` }} />
        </div>

        <ol className="stage-list" aria-label="处理阶段">
          {["created", "uploaded", "running", "completed"].map((stage) => (
            <li key={stage} className={stage === status ? "stage-list__item stage-list__item--current" : "stage-list__item"}>
              <span />
              {getStatusLabel(stage as JobStatus)}
            </li>
          ))}
        </ol>

        {errorMessage ? <p className="alert" role="alert">{errorMessage}</p> : null}
        {result?.status === "failed" && result.error_message ? (
          <p className="alert" role="alert">{result.error_message}</p>
        ) : null}
        {result?.status === "canceled" ? <p className="muted">任务已取消，不会继续处理。</p> : null}

        {downloadUrl ? (
          <a className="button button--success" href={downloadUrl}>
            下载结果压缩包
          </a>
        ) : null}
      </div>

      <div className="log-panel">
        <div className="panel-heading">
          <p className="eyebrow">关键日志</p>
          <h2>任务事件</h2>
        </div>
        {events.length > 0 ? (
          <ol className="log-list">
            {events.map((event) => (
              <li key={event.id}>
                <span>{event.event_type}</span>
                <p>{event.message}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty-state">任务创建后会在这里显示排队、推理和打包等关键日志。</p>
        )}
      </div>
    </section>
  );
}
