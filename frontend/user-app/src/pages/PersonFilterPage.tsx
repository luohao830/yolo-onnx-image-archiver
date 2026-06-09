import { useState } from "react";

import { createJob, type CreateJobResponse } from "../api/client";
import { ReceiptPanel } from "../components/ReceiptPanel";
import { UploadField } from "../components/UploadField";


type JobReceipt = Pick<CreateJobResponse, "job_code" | "access_token" | "status">;

export function PersonFilterPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [receipt, setReceipt] = useState<JobReceipt | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!selectedFile || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setReceipt(null);

    try {
      const created = await createJob("person_filter");
      setReceipt(created);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "创建任务失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h1>人员筛选模式</h1>
      <p>上传图片或压缩包后，系统会先创建任务并返回查询凭证。</p>
      <UploadField
        id="person-filter-upload"
        label="上传图片或压缩包"
        accept="image/*,.zip"
        selectedFile={selectedFile}
        onFileChange={setSelectedFile}
      />
      <button type="button" disabled={!selectedFile || isSubmitting} onClick={handleSubmit}>
        {isSubmitting ? "创建中..." : "开始处理"}
      </button>
      <p>当前阶段先打通任务创建与回执展示，文件上传接口会在后续任务接入。</p>
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      {receipt ? <ReceiptPanel receipt={receipt} /> : null}
    </main>
  );
}
