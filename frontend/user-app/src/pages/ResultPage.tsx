import { useMemo } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { JobProgressPanel } from "../components/JobProgressPanel";

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
    [props.accessToken, searchParams]
  );

  return (
    <main className="app-main">
      <section className="page-hero">
        <p className="eyebrow">处理进度</p>
        <h1>任务处理状态</h1>
        <p>系统会定时刷新处理进度和关键日志，任务完成后可下载结果压缩包。</p>
      </section>
      {jobCode.trim() && accessToken.trim() ? (
        <JobProgressPanel jobCode={jobCode} accessToken={accessToken} />
      ) : (
        <p className="alert" role="alert">任务状态不可用，请重新提交任务。</p>
      )}
    </main>
  );
}
