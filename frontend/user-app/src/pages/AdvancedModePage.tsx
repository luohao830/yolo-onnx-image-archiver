import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  createAdvancedJob,
  listPublishedModels,
  uploadJobFile,
  type AdvancedJobPayload,
  type CreateJobResponse,
  type JobStatus,
  type PublishedModel,
} from "../api/client";
import { JobProgressContainer } from "../components/job/JobProgressContainer";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Dropzone } from "../components/ui/dropzone";
import { FadeIn } from "../components/ui/fade-in";

type ActiveJob = Pick<CreateJobResponse, "job_code" | "access_token" | "status">;

const ACCEPT = "image/*,.zip";

export function AdvancedModePage() {
  const [models, setModels] = useState<PublishedModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [conf, setConf] = useState("0.25");
  const [iou, setIou] = useState("0.45");
  const [batch, setBatch] = useState("16");
  const [drawBoxes, setDrawBoxes] = useState(false);
  const [saveTxt, setSaveTxt] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadModels() {
      try {
        const loaded = await listPublishedModels();
        if (cancelled) return;
        setModels(loaded);
        setSelectedModelId((current) => current || loaded[0]?.id || "");
      } catch (error) {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : "加载模型失败");
      }
    }
    void loadModels();
    return () => {
      cancelled = true;
    };
  }, []);

  function validate(): string | null {
    const confNum = Number(conf);
    const iouNum = Number(iou);
    const batchNum = Number(batch);
    if (!selectedModelId) return "请选择模型";
    if (Number.isNaN(confNum) || confNum < 0 || confNum > 1) return "置信度阈值需在 0-1 之间";
    if (Number.isNaN(iouNum) || iouNum < 0 || iouNum > 1) return "IoU 阈值需在 0-1 之间";
    if (Number.isNaN(batchNum) || batchNum < 1 || !Number.isInteger(batchNum)) return "批处理大小需为正整数";
    if (files.length === 0) return "请上传图片或 zip 压缩包";
    return null;
  }

  async function handleSubmit() {
    const validationError = validate();
    if (validationError || isSubmitting) {
      setErrorMessage(validationError);
      if (validationError) return;
    }
    if (isSubmitting) return;

    setIsSubmitting(true);
    setErrorMessage(null);
    setActiveJob(null);

    try {
      const payload: AdvancedJobPayload = {
        conf: Number(conf),
        iou: Number(iou),
        batch: Number(batch),
        draw_boxes: drawBoxes,
        save_txt: saveTxt,
      };
      const created = await createAdvancedJob(Number(selectedModelId), payload);
      // 高级模式上传首个文件（图片或 zip）。
      const uploaded = await uploadJobFile(created.job_code, created.access_token, files[0]);
      setActiveJob({
        job_code: uploaded.job_code,
        access_token: created.access_token,
        status: uploaded.status,
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "创建任务失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-page">
      <main className="mx-auto grid w-[min(1120px,calc(100%-32px))] gap-6 py-8">
        <FadeIn>
          <section className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wide text-brand">高级模式</p>
            <h1 className="text-4xl font-bold leading-tight text-ink">选择模型并查看处理过程</h1>
            <p className="max-w-2xl text-sm leading-relaxed text-muted">
              使用管理员发布的模型和推理参数创建任务，提交后显示进度、关键日志和结果下载。
            </p>
          </section>
        </FadeIn>

        <FadeIn delay={0.05}>
          <Card>
            <CardHeader>
              <CardTitle>高级模式参数</CardTitle>
              <CardDescription>选择模型并配置推理参数，上传图片或 zip 后提交。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <div className="grid gap-4 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center">
                <label htmlFor="advanced-model" className="text-sm font-bold text-ink">选择模型</label>
                <select
                  id="advanced-model"
                  value={selectedModelId}
                  onChange={(event) => setSelectedModelId(event.target.value)}
                  className="w-full rounded-md border border-line-strong bg-card px-3 py-2.5 text-ink"
                >
                  <option value="" disabled>
                    {models.length > 0 ? "请选择模型" : "暂无已发布模型"}
                  </option>
                  {models.map((model) => (
                    <option key={model.id} value={model.id}>{model.name}</option>
                  ))}
                </select>

                <label htmlFor="advanced-conf" className="text-sm font-bold text-ink">置信度阈值</label>
                <input
                  id="advanced-conf"
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  value={conf}
                  onChange={(event) => setConf(event.target.value)}
                  className="w-full rounded-md border border-line-strong bg-card px-3 py-2.5 text-ink"
                />

                <label htmlFor="advanced-iou" className="text-sm font-bold text-ink">IoU 阈值</label>
                <input
                  id="advanced-iou"
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  value={iou}
                  onChange={(event) => setIou(event.target.value)}
                  className="w-full rounded-md border border-line-strong bg-card px-3 py-2.5 text-ink"
                />

                <label htmlFor="advanced-batch" className="text-sm font-bold text-ink">批处理大小</label>
                <input
                  id="advanced-batch"
                  type="number"
                  min={1}
                  step={1}
                  value={batch}
                  onChange={(event) => setBatch(event.target.value)}
                  className="w-full rounded-md border border-line-strong bg-card px-3 py-2.5 text-ink"
                />
              </div>

              <div className="flex flex-wrap gap-5">
                <label className="flex items-center gap-2 text-sm font-bold text-ink">
                  <input
                    type="checkbox"
                    checked={drawBoxes}
                    onChange={(event) => setDrawBoxes(event.target.checked)}
                    className="h-4 w-4 rounded border-line-strong"
                  />
                  绘制检测框
                </label>
                <label className="flex items-center gap-2 text-sm font-bold text-ink">
                  <input
                    type="checkbox"
                    checked={saveTxt}
                    onChange={(event) => setSaveTxt(event.target.checked)}
                    className="h-4 w-4 rounded border-line-strong"
                  />
                  保存标签 txt
                </label>
              </div>

              <Dropzone
                accept={ACCEPT}
                multiple={false}
                onFiles={(picked) => setFiles(picked)}
                hint="拖拽图片或 zip 压缩包到此处，或点击选择文件"
              />
              {files.length > 0 ? (
                <p className="text-sm text-muted">已选择：{files[0].name}</p>
              ) : null}

              <div className="flex items-center gap-3">
                <Button
                  variant="primary"
                  size="lg"
                  disabled={!selectedModelId || isSubmitting}
                  onClick={handleSubmit}
                >
                  {isSubmitting ? "创建中..." : "开始处理"}
                </Button>
                <Link
                  to="/"
                  className="inline-flex min-h-10 items-center justify-center rounded-md px-3.5 font-bold text-muted transition-colors hover:bg-slate-100 hover:text-ink"
                >
                  返回首页
                </Link>
              </div>
            </CardContent>
          </Card>
        </FadeIn>

        {errorMessage ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {errorMessage}
          </p>
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
