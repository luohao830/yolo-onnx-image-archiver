import { useState } from "react";
import { Link } from "react-router-dom";

import {
  createJob,
  uploadJobFile,
  type CreateJobResponse,
  type JobStatus
} from "../api/client";
import { JobProgressPanel } from "../components/JobProgressPanel";
import { UploadField } from "../components/UploadField";

type ActiveJob = Pick<CreateJobResponse, "job_code" | "access_token" | "status">;
type UploadPhase = "uploading" | "extracting";

interface UploadStage {
  phase: UploadPhase;
  progress: number;
}

function isZipFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".zip");
}

function getUploadStageLabel(phase: UploadPhase): string {
  const labels: Record<UploadPhase, string> = {
    uploading: "文件上传中",
    extracting: "正在解压"
  };

  return labels[phase];
}

export function HomePage() {
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
      const uploaded = await uploadJobFile(created.job_code, created.access_token, selectedFile, {
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
      <section className="page-hero page-hero--with-action">
        <div>
          <p className="eyebrow">内网图片处理工作台</p>
          <h1>上传图片后直接查看处理进度</h1>
          <p>选择图片或压缩包，提交后系统会按 batch 推理并实时反馈进度、关键日志和结果下载入口。</p>
        </div>
        <Link className="button button--secondary admin-entry" to="/admin/configs">
          管理员配置
        </Link>
      </section>

      <section className="work-card">
        <div className="panel-heading">
          <p className="eyebrow">输入文件</p>
          <h2>创建图片处理任务</h2>
        </div>
        <UploadField
          id="image-upload"
          label="上传图片或压缩包"
          accept="image/*,.zip"
          selectedFile={selectedFile}
          onFileChange={setSelectedFile}
        />
        <button className="button button--primary" type="button" disabled={!selectedFile || isSubmitting} onClick={handleSubmit}>
          {isSubmitting ? "提交中..." : "开始处理"}
        </button>
        <p className="muted">推荐上传 zip 压缩包。任务进入队列后，推理进度会按已处理图片数持续更新。</p>
      </section>

      {errorMessage ? <p className="alert" role="alert">{errorMessage}</p> : null}
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
