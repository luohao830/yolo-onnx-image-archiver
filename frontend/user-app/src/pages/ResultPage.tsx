import { useMemo } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { JobProgressContainer } from "../components/job/JobProgressContainer";
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

  return (
    <div className="min-h-screen bg-page">
      <main className="mx-auto grid w-[min(1120px,calc(100%-32px))] gap-6 py-8">
        <FadeIn>
          <section className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wide text-brand">处理进度</p>
            <h1 className="text-4xl font-bold leading-tight text-ink">任务处理状态</h1>
            <p className="max-w-2xl text-sm leading-relaxed text-muted">
              系统会实时推送并定时刷新处理进度和关键日志，任务完成后可下载结果压缩包。
            </p>
          </section>
        </FadeIn>

        {jobCode.trim() && accessToken.trim() ? (
          <FadeIn delay={0.05}>
            <JobProgressContainer jobCode={jobCode} accessToken={accessToken} />
          </FadeIn>
        ) : (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            任务状态不可用，请重新提交任务。
          </p>
        )}
      </main>
    </div>
  );
}
