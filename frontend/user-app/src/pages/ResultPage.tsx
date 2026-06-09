import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { getJobStatus, type JobStatus, type PublicJobStatus } from "../api/client";
import { StatusTimeline } from "../components/StatusTimeline";

const POLL_INTERVAL_MS = 2000;

export interface ResultPageProps {
  jobCode?: string;
  accessToken?: string;
}

function isTerminalStatus(status: JobStatus): boolean {
  return status === "completed" || status === "failed";
}

export function ResultPage(props: ResultPageProps) {
  const params = useParams<{ jobCode: string }>();
  const [searchParams] = useSearchParams();
  const [result, setResult] = useState<PublicJobStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const jobCode = useMemo(() => props.jobCode ?? params.jobCode ?? "", [params.jobCode, props.jobCode]);
  const accessToken = useMemo(
    () => props.accessToken ?? searchParams.get("access_token") ?? "",
    [props.accessToken, searchParams]
  );

  useEffect(() => {
    if (!jobCode.trim() || !accessToken.trim()) {
      setResult(null);
      setErrorMessage("缺少任务编号或访问口令");
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

  return (
    <main>
      <h1>任务结果</h1>
      <p>系统会定时刷新任务状态，直到任务完成或失败。</p>
      <p>任务编号：{jobCode || "未提供"}</p>
      {!result && isLoading ? <p>正在获取最新状态...</p> : null}
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      {result ? (
        <section aria-label="任务结果状态">
          <h2>当前状态</h2>
          <p>{result.status}</p>
          <h2>任务模式</h2>
          <p>{result.mode}</p>
          <StatusTimeline status={result.status} />
          {result.status === "completed" ? (
            <p>结果包已生成，可在后续步骤接入下载按钮。</p>
          ) : null}
          {result.status === "failed" && result.error_message ? (
            <p role="alert">{result.error_message}</p>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
