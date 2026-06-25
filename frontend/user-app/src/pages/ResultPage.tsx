import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import {
  getJobDetections,
  type JobDetectionsResponse,
  type PublicJobStatus,
} from "../api/client";
import type { JobDetection, JobStats, JobStatus } from "../api/types";
import { DetectionImageViewer } from "../components/job/DetectionImageViewer";
import { JobProgressContainer } from "../components/job/JobProgressContainer";
import { StatsPanel } from "../components/job/StatsPanel";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { FadeIn } from "../components/ui/fade-in";

export interface ResultPageProps {
  jobCode?: string;
  accessToken?: string;
}

export function ResultPage(props: ResultPageProps) {
  const params = useParams<{ jobCode: string }>();
  const [searchParams] = useSearchParams();

  const jobCode = useMemo(() => props.jobCode ?? params.jobCode ?? "", [params.jobCode, props.jobCode]);
  const accessToken = useMemo(
    () => props.accessToken ?? searchParams.get("access_token") ?? "",
    [props.accessToken, searchParams],
  );

  const [status, setStatus] = useState<JobStatus>("created");
  const [summary, setSummary] = useState<JobStats | null>(null);
  const [detections, setDetections] = useState<JobDetection[]>([]);
  const [detectionsError, setDetectionsError] = useState<string | null>(null);
  const detectionsLoadedRef = useRef(false);

  useEffect(() => {
    setStatus("created");
    setSummary(null);
    setDetections([]);
    setDetectionsError(null);
    detectionsLoadedRef.current = false;
  }, [jobCode, accessToken]);

  const handleStatus = useCallback(
    (next: PublicJobStatus) => {
      setStatus(next.status);
      setSummary(next.summary ?? null);
      if (next.status === "completed" && !detectionsLoadedRef.current) {
        detectionsLoadedRef.current = true;
        try {
          getJobDetections(jobCode, accessToken)
            .then((data: JobDetectionsResponse) => setDetections(data.images ?? []))
            .catch((error) =>
              setDetectionsError(error instanceof Error ? error.message : "加载检测结果失败"),
            );
        } catch (error) {
          setDetectionsError(error instanceof Error ? error.message : "加载检测结果失败");
        }
      }
    },
    [jobCode, accessToken],
  );

  const hasDetections = detections.length > 0;

  return (
    <div className="min-h-screen bg-page">
      <main className="mx-auto grid w-[min(1120px,calc(100%-32px))] gap-6 py-8">
        <FadeIn>
          <section className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wide text-brand">处理进度</p>
            <h1 className="text-4xl font-bold leading-tight text-ink">任务处理状态</h1>
            <p className="max-w-2xl text-sm leading-relaxed text-muted">
              系统会实时推送并定时刷新处理进度和关键日志，任务完成后可下载结果压缩包并查看检测结果。
            </p>
          </section>
        </FadeIn>

        {jobCode.trim() && accessToken.trim() ? (
          <FadeIn delay={0.05}>
            <JobProgressContainer
              jobCode={jobCode}
              accessToken={accessToken}
              onStatus={handleStatus}
            />
          </FadeIn>
        ) : (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            任务状态不可用，请重新提交任务。
          </p>
        )}

        {status === "completed" ? (
          <>
            {detectionsError ? (
              <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700" role="alert">
                {detectionsError}
              </p>
            ) : null}

            {hasDetections ? (
              <FadeIn delay={0.1}>
                <Card>
                  <CardHeader>
                    <CardTitle>检测结果可视化</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DetectionImageViewer
                      jobCode={jobCode}
                      accessToken={accessToken}
                      detections={detections}
                    />
                  </CardContent>
                </Card>
              </FadeIn>
            ) : null}

            <FadeIn delay={0.15}>
              <StatsPanel summary={summary} detections={detections} />
            </FadeIn>
          </>
        ) : null}
      </main>
    </div>
  );
}
