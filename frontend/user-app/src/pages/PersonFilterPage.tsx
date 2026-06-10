import { useState } from "react";

import { createJob, uploadJobFile, type CreateJobResponse, type JobStatus } from "../api/client";
import { JobProgressPanel } from "../components/JobProgressPanel";
import { UploadField } from "../components/UploadField";


type ActiveJob = Pick<CreateJobResponse, "job_code" | "access_token" | "status">;

export function PersonFilterPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!selectedFile || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setActiveJob(null);

    try {
      const created = await createJob("person_filter");
      const uploaded = await uploadJobFile(created.job_code, created.access_token, selectedFile);
      setActiveJob({
        job_code: uploaded.job_code,
        access_token: created.access_token,
        status: uploaded.status
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "提交任务失败");
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
