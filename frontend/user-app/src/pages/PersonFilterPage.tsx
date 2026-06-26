import { useState } from "react";

import {
  createJob,
  uploadJobFile,
  type CreateJobResponse,
  type JobStatus,
} from "../api/client";
import { JobProgressContainer } from "../components/job/JobProgressContainer";
import { UploadField } from "../components/UploadField";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { FadeIn } from "../components/ui/fade-in";
import { Progress } from "../components/ui/progress";
import { cn } from "../lib/utils";

type ActiveJob = Pick<CreateJobResponse, "job_code" | "access_token" | "status">;
type UploadPhase = "uploading" | "extracting";

interface UploadStage {
  phase: UploadPhase;
  progress: number;
}

function isZipFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".zip");
}

const PHASE_LABELS: Record<UploadPhase, string> = {
  uploading: "文件上传中",
  extracting: "正在解压",
};

interface PersonFilterPageProps {
  /** 嵌入首页时隐藏外层 hero 与容器边距。 */
  embedded?: boolean;
}

export function PersonFilterPage({ embedded = false }: PersonFilterPageProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [uploadStage, setUploadStage] = useState<UploadStage | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!selectedFile || isSubmitting) return;
    setIsSubmitting(true);
    setErrorMessage(null);
    setActiveJob(null);
    setUploadStage({ phase: "uploading", progress: 0 });

    try {
      const created = await createJob("person_filter");
      setUploadStage({ phase: "uploading", progress: 0 });
      const uploaded = await uploadJobFile(created.job_code, created.access_token, selectedFile, {
        onProgress: (progress) => {
          setUploadStage({
            phase: progress >= 100 && isZipFile(selectedFile) ? "extracting" : "uploading",
            progress,
          });
        },
      });
      setActiveJob({
        job_code: uploaded.job_code,
        access_token: created.access_token,
        status: uploaded.status,
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
    <div className={cn(!embedded && "min-h-screen bg-page")}>
      <main className={cn("mx-auto grid w-[min(1120px,calc(100%-32px))] gap-6", !embedded && "py-8")}>
        {!embedded ? (
          <FadeIn>
            <section className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-wide text-brand">人员筛选模式</p>
              <h1 className="text-4xl font-bold leading-tight text-ink">上传图片后查看处理进度</h1>
              <p className="max-w-2xl text-sm leading-relaxed text-muted">
                提交任务后，页面会显示处理进度、关键日志，并在完成后提供结果压缩包下载。
              </p>
            </section>
          </FadeIn>
        ) : null}

        <FadeIn delay={0.05}>
          <Card>
            <CardHeader>
              <CardTitle>创建人员筛选任务</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <UploadField
                id="person-filter-upload"
                label="上传图片或压缩包"
                accept="image/*,.zip"
                selectedFile={selectedFile}
                onFileChange={setSelectedFile}
              />
              <Button
                variant="primary"
                size="lg"
                className="self-start"
                disabled={!selectedFile || isSubmitting}
                onClick={handleSubmit}
              >
                {isSubmitting ? "提交中..." : "开始处理"}
              </Button>
              <p className="text-sm leading-relaxed text-muted">
                上传成功后任务会进入队列，并在这里显示处理进度和结果下载入口。
              </p>
            </CardContent>
          </Card>
        </FadeIn>

        {errorMessage ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {errorMessage}
          </p>
        ) : null}

        {uploadStage ? (
          <FadeIn delay={0.05}>
            <Card className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-xs font-bold uppercase tracking-wide text-brand">处理状态</p>
                  <h2 className="text-lg font-bold text-ink">{PHASE_LABELS[uploadStage.phase]}</h2>
                </div>
                <span className="text-3xl font-bold leading-none text-ink">{uploadStage.progress}%</span>
              </div>
              <div className="mt-4">
                <Progress
                  value={uploadStage.progress}
                  active={uploadStage.phase === "uploading"}
                  aria-label="上传阶段进度"
                />
              </div>
            </Card>
          </FadeIn>
        ) : null}

        {activeJob ? (
          <FadeIn delay={0.05}>
            <JobProgressContainer
              jobCode={activeJob.job_code}
              accessToken={activeJob.access_token}
              initialStatus={activeJob.status as JobStatus}
            />
          </FadeIn>
        ) : null}
      </main>
    </div>
  );
}
