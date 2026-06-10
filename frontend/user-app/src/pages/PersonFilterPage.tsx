import { useState } from "react";

import {
  calculateFileSha256,
  createJob,
  reuseUploadedArchive,
  uploadJobFile,
  type CreateJobResponse,
  type JobStatus
} from "../api/client";
import { JobProgressPanel } from "../components/JobProgressPanel";
import { UploadField } from "../components/UploadField";


type ActiveJob = Pick<CreateJobResponse, "job_code" | "access_token" | "status">;
type UploadPhase = "hashing" | "reusing" | "uploading" | "extracting";
const MAX_PREUPLOAD_HASH_BYTES = 512 * 1024 * 1024;

interface UploadStage {
  phase: UploadPhase;
  progress: number;
}

function isZipFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".zip");
}

function shouldCheckUploadReuse(file: File): boolean {
  return isZipFile(file) && file.size <= MAX_PREUPLOAD_HASH_BYTES;
}

function getUploadStageLabel(phase: UploadPhase): string {
  const labels: Record<UploadPhase, string> = {
    hashing: "计算文件指纹",
    reusing: "检查复用缓存",
    uploading: "文件上传中",
    extracting: "正在解压"
  };

  return labels[phase];
}

export function PersonFilterPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [uploadStage, setUploadStage] = useState<UploadStage | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!selectedFile || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setActiveJob(null);
    setUploadStage({ phase: "uploading", progress: 0 });

    try {
      const created = await createJob("person_filter");
      let contentSha256: string | undefined;

      if (shouldCheckUploadReuse(selectedFile)) {
        setUploadStage({ phase: "hashing", progress: 0 });
        contentSha256 = await calculateFileSha256(selectedFile);
        setUploadStage({ phase: "reusing", progress: 100 });
        const reused = await reuseUploadedArchive(created.job_code, created.access_token, contentSha256);
        if (reused) {
          setActiveJob({
            job_code: reused.job_code,
            access_token: created.access_token,
            status: reused.status
          });
          setUploadStage(null);
          return;
        }
      }

      setUploadStage({ phase: "uploading", progress: 0 });
      const uploaded = await uploadJobFile(created.job_code, created.access_token, selectedFile, {
        contentSha256,
        onProgress: (progress) => {
          setUploadStage({
            phase: progress >= 100 && isZipFile(selectedFile) ? "extracting" : "uploading",
            progress
          });
        }
      });
      setActiveJob({
        job_code: uploaded.job_code,
        access_token: created.access_token,
        status: uploaded.status
      });
      setUploadStage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "提交任务失败");
      setUploadStage(null);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="app-main">
      <section className="page-hero">
        <p className="eyebrow">人员筛选模式</p>
        <h1>上传图片后查看处理进度</h1>
        <p>提交任务后，页面会显示处理进度、关键日志，并在完成后提供结果压缩包下载。</p>
      </section>

      <section className="work-card">
        <div className="panel-heading">
          <p className="eyebrow">输入文件</p>
          <h2>创建人员筛选任务</h2>
        </div>
        <UploadField
          id="person-filter-upload"
          label="上传图片或压缩包"
          accept="image/*,.zip"
          selectedFile={selectedFile}
          onFileChange={setSelectedFile}
        />
        <button className="button button--primary" type="button" disabled={!selectedFile || isSubmitting} onClick={handleSubmit}>
          {isSubmitting ? "提交中..." : "开始处理"}
        </button>
        <p className="muted">上传成功后任务会进入队列，并在这里显示处理进度和结果下载入口。</p>
      </section>

      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      {uploadStage ? (
        <section className="status-panel" aria-label="上传处理状态">
          <div className="status-panel__header">
            <div>
              <p className="eyebrow">处理状态</p>
              <h2>{getUploadStageLabel(uploadStage.phase)}</h2>
            </div>
            <span className="status-badge status-badge--uploaded">{uploadStage.phase}</span>
          </div>
          <div className="progress-summary">
            <strong>{uploadStage.progress}%</strong>
            <span>当前阶段进度</span>
          </div>
          <div
            className="progress-track"
            role="progressbar"
            aria-label="上传阶段进度"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={uploadStage.progress}
          >
            <span style={{ width: `${uploadStage.progress}%` }} />
          </div>
          <ol className="stage-list" aria-label="上传阶段">
            {(["uploading", "extracting", "running"] as const).map((stage) => (
              <li
                key={stage}
                className={
                  (stage === "running" && uploadStage.phase === "extracting") || stage === uploadStage.phase
                    ? "stage-list__item stage-list__item--current"
                    : "stage-list__item"
                }
              >
                <span />
                {stage === "running" ? "处理" : getUploadStageLabel(stage)}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      {activeJob ? (
        <JobProgressPanel
          jobCode={activeJob.job_code}
          accessToken={activeJob.access_token}
          initialStatus={activeJob.status as JobStatus}
        />
      ) : null}
    </main>
  );
}
