import { useEffect, useState } from "react";

import {
  cancelAdminJob,
  downloadAdminJobResult,
  getAdminJob,
  listAdminJobs,
  retryAdminJob,
  type AdminJob,
  type AdminJobDetail
} from "../../admin-api/client";

export function JobsPage() {
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<AdminJobDetail | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    void loadJobs();
  }, []);

  async function loadJobs() {
    if (isRefreshing) {
      return;
    }

    setIsRefreshing(true);
    try {
      const loaded = await listAdminJobs();
      setJobs(loaded);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "加载任务列表失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleCancel(jobId: number) {
    const updated = await cancelAdminJob(jobId);
    setJobs((current) => current.map((job) => (job.id === updated.id ? updated : job)));
    setSelectedJob((current) => (current?.id === updated.id ? { ...current, ...updated } : current));
  }

  async function handleRetry(jobId: number) {
    const updated = await retryAdminJob(jobId);
    setJobs((current) => current.map((job) => (job.id === updated.id ? updated : job)));
    setSelectedJob((current) => (current?.id === updated.id ? { ...current, ...updated } : current));
  }

  async function handleShowDetail(jobId: number) {
    try {
      const detail = await getAdminJob(jobId);
      setSelectedJob(detail);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "加载任务详情失败");
    }
  }

  async function handleDownload(jobId: number) {
    try {
      setDownloadMessage(null);
      await downloadAdminJobResult(jobId);
    } catch (error) {
      setDownloadMessage(error instanceof Error ? error.message : "下载输出结果失败");
    }
  }

  return (
    <section className="admin-page">
      <div className="page-heading page-heading--with-action">
        <div>
          <p className="eyebrow">任务监控</p>
          <h1>任务监控</h1>
          <p>查看任务状态、进度、错误、关键日志和输出结果。</p>
        </div>
        <button className="button button--secondary" type="button" onClick={() => void loadJobs()} disabled={isRefreshing}>
          {isRefreshing ? "刷新中..." : "刷新任务"}
        </button>
      </div>

      {errorMessage ? <p className="alert" role="alert">{errorMessage}</p> : null}
      {downloadMessage ? <p className="alert" role="alert">{downloadMessage}</p> : null}

      <div className="jobs-layout">
        <div className="table-card" role="table" aria-label="任务列表">
          <div className="job-row job-row--head" role="row">
            <span>任务</span>
            <span>模式</span>
            <span>状态</span>
            <span>进度</span>
            <span>操作</span>
          </div>
          {jobs.length > 0 ? (
            jobs.map((job) => (
              <div className="job-row" role="row" key={job.id}>
                <strong>{job.job_code}</strong>
                <span>{job.mode}</span>
                <span className={`status-badge status-badge--${job.status}`}>
                  {job.cancel_requested ? "已请求取消" : job.status}
                </span>
                <span>{job.progress}%</span>
                <div className="row-actions">
                  <button className="button button--secondary" type="button" onClick={() => void handleShowDetail(job.id)}>
                    查看详情
                  </button>
                  <button className="button button--secondary" type="button" onClick={() => void handleCancel(job.id)}>
                    取消
                  </button>
                  {job.status === "failed" ? (
                    <button className="button button--primary" type="button" onClick={() => void handleRetry(job.id)}>
                      重试
                    </button>
                  ) : null}
                  {job.download_ready ? (
                    <button className="button button--success" type="button" onClick={() => void handleDownload(job.id)}>
                      下载
                    </button>
                  ) : null}
                </div>
              </div>
            ))
          ) : (
            <p className="empty-state">暂无任务。用户提交图片处理后会显示在这里。</p>
          )}
        </div>

        <aside className="detail-panel" aria-label="任务详情">
          {selectedJob ? (
            <>
              <div className="panel-heading">
                <p className="eyebrow">任务详情</p>
                <h2>{selectedJob.job_code}</h2>
              </div>
              <dl className="detail-list">
                <div>
                  <dt>模式</dt>
                  <dd>{selectedJob.mode}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>{selectedJob.status}</dd>
                </div>
                <div>
                  <dt>进度</dt>
                  <dd>{selectedJob.progress}%</dd>
                </div>
                <div>
                  <dt>输入</dt>
                  <dd>{selectedJob.input_path ?? "未记录"}</dd>
                </div>
                <div>
                  <dt>结果目录</dt>
                  <dd>{selectedJob.result_dir ?? "未生成"}</dd>
                </div>
              </dl>
              {selectedJob.error_message ? <p className="alert" role="alert">{selectedJob.error_message}</p> : null}
              {selectedJob.download_ready ? (
                <button className="button button--success" type="button" onClick={() => void handleDownload(selectedJob.id)}>
                  下载输出结果
                </button>
              ) : (
                <p className="muted">任务完成并生成结果包后可以下载输出结果。</p>
              )}
              <div className="log-panel log-panel--embedded">
                <h3>关键日志</h3>
                {selectedJob.events.length > 0 ? (
                  <ol className="log-list">
                    {selectedJob.events.map((event) => (
                      <li key={event.id}>
                        <span>{event.event_type}</span>
                        <p>{event.message}</p>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="muted">暂无任务事件。</p>
                )}
              </div>
            </>
          ) : (
            <p className="muted">选择一个任务查看详情、关键日志和结果下载状态。</p>
          )}
        </aside>
      </div>
    </section>
  );
}
