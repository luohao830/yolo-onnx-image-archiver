import { useEffect, useState } from "react";

import { createJob, listPublishedModels, type CreateJobResponse, type JobStatus, type PublishedModel } from "../api/client";
import { JobProgressPanel } from "../components/JobProgressPanel";

type ActiveJob = Pick<CreateJobResponse, "job_code" | "access_token" | "status">;

export function AdvancedModePage() {
  const [models, setModels] = useState<PublishedModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [conf, setConf] = useState("0.25");
  const [iou, setIou] = useState("0.45");
  const [batch, setBatch] = useState("16");
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadModels() {
      try {
        const loadedModels = await listPublishedModels();

        if (cancelled) {
          return;
        }

        setModels(loadedModels);
        setSelectedModelId((current) => current || loadedModels[0]?.id || "");
      } catch (error) {
        if (cancelled) {
          return;
        }

        setErrorMessage(error instanceof Error ? error.message : "加载模型失败");
      }
    }

    void loadModels();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit() {
    if (!selectedModelId || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setActiveJob(null);

    try {
      const created = await createJob("advanced");
      setActiveJob(created);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "创建任务失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="app-main">
      <section className="page-hero">
        <p className="eyebrow">高级模式</p>
        <h1>选择模型并查看处理过程</h1>
        <p>使用管理员发布的模型和推理参数创建任务，提交后显示进度、关键日志和结果下载。</p>
      </section>

      <section className="work-card">
        <div className="form-grid">
          <label htmlFor="advanced-model">选择模型</label>
          <select
            id="advanced-model"
            value={selectedModelId}
            onChange={(event) => setSelectedModelId(event.target.value)}
          >
            <option value="" disabled>
              {models.length > 0 ? "请选择模型" : "暂无已发布模型"}
            </option>
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
          <label htmlFor="advanced-conf">置信度阈值</label>
          <input
            id="advanced-conf"
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={conf}
            onChange={(event) => setConf(event.target.value)}
          />
          <label htmlFor="advanced-iou">IoU 阈值</label>
          <input
            id="advanced-iou"
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={iou}
            onChange={(event) => setIou(event.target.value)}
          />
          <label htmlFor="advanced-batch">批处理大小</label>
          <input
            id="advanced-batch"
            type="number"
            min="1"
            step="1"
            value={batch}
            onChange={(event) => setBatch(event.target.value)}
          />
        </div>
        <button className="button button--primary" type="button" disabled={!selectedModelId || isSubmitting} onClick={handleSubmit}>
          {isSubmitting ? "创建中..." : "开始处理"}
        </button>
        <p className="muted">当前 API 创建任务时只接收高级模式，具体模型和参数提交会随任务上传链路完善。</p>
      </section>
      {errorMessage ? <p className="alert" role="alert">{errorMessage}</p> : null}
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
