import { RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  cancelAdminJob,
  downloadAdminJobResult,
  getAdminJob,
  listAdminJobs,
  retryAdminJob,
  subscribeAdminJobEvents,
  type AdminJob,
  type AdminJobDetail,
  type JobStats,
} from "../../admin-api/client";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { EmptyState } from "../../components/ui/empty-state";
import { FadeIn } from "../../components/ui/fade-in";
import { KpiCard } from "../../components/job/KpiCard";
import { LogPanel } from "../../components/job/LogPanel";
import { Progress } from "../../components/ui/progress";
import { StatusBadge } from "../../components/job/StatusBadge";
import type { JobStatus } from "../../api/client";

const POLL_INTERVAL_MS = 3000;

function formatSeconds(value?: number): string {
  if (value === undefined || value === null) return "—";
  if (value < 1) return `${(value * 1000).toFixed(0)} ms`;
  return `${value.toFixed(2)} s`;
}

export function JobsPage() {
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<AdminJobDetail | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    void loadJobs();
  }, []);

  // 选中任务后定时轮询详情 + SSE 订阅。
  useEffect(() => {
    if (!selectedJob) return;
    const jobId = selectedJob.id;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function refreshDetail() {
      try {
        const detail = await getAdminJob(jobId);
        if (!stopped) setSelectedJob(detail);
      } catch {
        // 忽略瞬时错误，下一轮重试。
      }
    }

    let unsubscribe: (() => void) | null = null;
    try {
      unsubscribe = subscribeAdminJobEvents(jobId, () => {
        if (!stopped) void refreshDetail();
      });
    } catch {
      // SSE 不可用时降级轮询。
    }

    const schedule = () => {
      timer = setTimeout(() => {
        void refreshDetail();
        if (!stopped) schedule();
      }, POLL_INTERVAL_MS);
    };
    if (selectedJob.status !== "completed" && selectedJob.status !== "failed" && selectedJob.status !== "canceled") {
      schedule();
    }

    return () => {
      stopped = true;
      try {
        unsubscribe?.();
      } catch {
        // ignore
      }
      if (timer) clearTimeout(timer);
    };
  }, [selectedJob?.id, selectedJob?.status]);

  async function loadJobs() {
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      setJobs(await listAdminJobs());
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "加载任务列表失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleCancel(jobId: number) {
    try {
      const updated = await cancelAdminJob(jobId);
      setJobs((current) => current.map((job) => (job.id === updated.id ? updated : job)));
      setSelectedJob((current) => (current?.id === updated.id ? { ...current, ...updated } : current));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "取消任务失败");
    }
  }

  async function handleRetry(jobId: number) {
    try {
      const updated = await retryAdminJob(jobId);
      setJobs((current) => current.map((job) => (job.id === updated.id ? updated : job)));
      setSelectedJob((current) => (current?.id === updated.id ? { ...current, ...updated } : current));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "重试任务失败");
    }
  }

  async function handleShowDetail(jobId: number) {
    try {
      setSelectedJob(await getAdminJob(jobId));
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

  const filteredJobs = useMemo(() => {
    const keyword = filter.trim().toLowerCase();
    return jobs.filter((job) => {
      if (statusFilter !== "all" && job.status !== statusFilter) return false;
      if (!keyword) return true;
      return (
        job.job_code.toLowerCase().includes(keyword) ||
        job.mode.toLowerCase().includes(keyword)
      );
    });
  }, [jobs, filter, statusFilter]);

  const summary: JobStats | null = selectedJob?.summary ?? null;

  return (
    <section className="mx-auto grid w-[min(1280px,calc(100%-32px))] gap-5 py-7">
      <FadeIn>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <p className="text-xs font-bold uppercase tracking-wide text-brand">任务监控</p>
            <h1 className="text-3xl font-bold text-ink">任务监控</h1>
            <p className="max-w-2xl text-sm leading-relaxed text-muted">查看任务状态、进度、错误、关键日志与输出结果。</p>
          </div>
          <Button variant="secondary" size="md" onClick={() => void loadJobs()} disabled={isRefreshing}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            {isRefreshing ? "刷新中..." : "刷新任务"}
          </Button>
        </div>
      </FadeIn>

      {errorMessage ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{errorMessage}</p>
      ) : null}
      {downloadMessage ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{downloadMessage}</p>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <FadeIn delay={0.05}>
          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center gap-3 border-b border-line p-3">
              <div className="flex items-center gap-2 rounded-md border border-line-strong bg-card px-2">
                <Search className="h-4 w-4 text-slate-400" aria-hidden />
                <input
                  type="search"
                  placeholder="搜索 job_code 或模式"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                  className="min-w-48 bg-transparent py-2 text-sm text-ink outline-none"
                />
              </div>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="rounded-md border border-line-strong bg-card px-3 py-2 text-sm text-ink"
              >
                <option value="all">全部状态</option>
                {["created", "uploaded", "running", "completed", "failed", "canceled"].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-[1.1fr_0.75fr_0.75fr_0.5fr_minmax(200px,1fr)] gap-3 border-b border-line bg-page px-4 py-3 text-xs font-bold uppercase tracking-wide text-subtle">
              <span>任务</span>
              <span>模式</span>
              <span>状态</span>
              <span>进度</span>
              <span>操作</span>
            </div>

            {filteredJobs.length === 0 ? (
              <EmptyState title="暂无任务" description="用户提交图片处理后会显示在这里。" />
            ) : (
              filteredJobs.map((job) => (
                <div
                  key={job.id}
                  className="grid grid-cols-[1.1fr_0.75fr_0.75fr_0.5fr_minmax(200px,1fr)] items-center gap-3 border-b border-line px-4 py-3 last:border-b-0"
                >
                  <div className="flex flex-col">
                    <strong className="text-sm text-ink">{job.job_code}</strong>
                    {job.cancel_requested ? <span className="text-xs text-amber-600">已请求取消</span> : null}
                  </div>
                  <span className="text-sm text-muted">{job.mode}</span>
                  <StatusBadge status={job.status as JobStatus} />
                  <span className="text-sm font-bold text-ink">{job.progress}%</span>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" size="sm" onClick={() => void handleShowDetail(job.id)}>详情</Button>
                    <Button variant="ghost" size="sm" onClick={() => void handleCancel(job.id)}>取消</Button>
                    {job.status === "failed" ? (
                      <Button variant="secondary" size="sm" onClick={() => void handleRetry(job.id)}>重试</Button>
                    ) : null}
                    {job.download_ready ? (
                      <Button variant="success" size="sm" onClick={() => void handleDownload(job.id)}>下载</Button>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </Card>
        </FadeIn>

        <FadeIn delay={0.1}>
          <Card className="flex flex-col gap-4 p-4">
            {selectedJob ? (
              <>
                <div className="space-y-1">
                  <p className="text-xs font-bold uppercase tracking-wide text-brand">任务详情</p>
                  <h2 className="text-lg font-bold text-ink">{selectedJob.job_code}</h2>
                </div>
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <dt className="text-subtle">模式</dt>
                  <dd className="text-ink">{selectedJob.mode}</dd>
                  <dt className="text-subtle">状态</dt>
                  <dd><StatusBadge status={selectedJob.status as JobStatus} /></dd>
                  <dt className="text-subtle">进度</dt>
                  <dd className="text-ink">{selectedJob.progress}%</dd>
                  <dt className="text-subtle col-span-2">输入</dt>
                  <dd className="col-span-2 break-all text-ink">{selectedJob.input_path ?? "未记录"}</dd>
                </dl>
                <Progress value={selectedJob.progress} active={selectedJob.status === "running"} />

                {selectedJob.error_message ? (
                  <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
                    {selectedJob.error_message}
                  </p>
                ) : null}

                {selectedJob.status === "completed" && summary ? (
                  <div className="grid grid-cols-2 gap-2">
                    <KpiCard title="总图数" value={summary.total ?? "—"} />
                    <KpiCard title="已写入" value={summary.written ?? "—"} />
                    <KpiCard title="耗时" value={formatSeconds(summary.elapsed_sec)} />
                    <KpiCard title="设备" value={summary.cuda_enabled ? "CUDA" : "CPU"} />
                  </div>
                ) : null}

                {selectedJob.download_ready ? (
                  <Button variant="success" size="md" onClick={() => void handleDownload(selectedJob.id)}>
                    下载输出结果
                  </Button>
                ) : (
                  <p className="text-xs text-muted">任务完成并生成结果包后可以下载输出结果。</p>
                )}

                <LogPanel events={selectedJob.events} />
              </>
            ) : (
              <EmptyState title="选择任务查看详情" description="点击左侧任务的「详情」查看进度、日志与结果下载。" />
            )}
          </Card>
        </FadeIn>
      </div>
    </section>
  );
}
