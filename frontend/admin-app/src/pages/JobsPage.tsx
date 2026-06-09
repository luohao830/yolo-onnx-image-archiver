import { useEffect, useState } from "react";

import { cancelAdminJob, listAdminJobs, retryAdminJob, type AdminJob } from "../api/client";

export function JobsPage() {
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadJobs() {
      try {
        const loaded = await listAdminJobs();
        if (!cancelled) {
          setJobs(loaded);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "加载任务列表失败");
        }
      }
    }

    void loadJobs();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCancel(jobId: number) {
    const updated = await cancelAdminJob(jobId);
    setJobs((current) => current.map((job) => (job.id === updated.id ? updated : job)));
  }

  async function handleRetry(jobId: number) {
    const updated = await retryAdminJob(jobId);
    setJobs((current) => current.map((job) => (job.id === updated.id ? updated : job)));
  }

  return (
    <section>
      <h1>任务监控</h1>
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      <ul>
        {jobs.map((job) => (
          <li key={job.id}>
            <strong>{job.job_code}</strong>
            <p>{job.cancel_requested ? "已请求取消" : job.status}</p>
            {job.error_message ? <p>{job.error_message}</p> : null}
            <button type="button" onClick={() => void handleCancel(job.id)}>
              取消任务
            </button>
            {job.status === "failed" ? (
              <button type="button" onClick={() => void handleRetry(job.id)}>
                重试任务
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
