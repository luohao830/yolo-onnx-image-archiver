import { useEffect, useState } from "react";

import { listPublishedModels, type PublishedModel } from "../api/client";

export function AdvancedModePage() {
  const [models, setModels] = useState<PublishedModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [conf, setConf] = useState("0.25");
  const [iou, setIou] = useState("0.45");
  const [batch, setBatch] = useState("16");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  return (
    <main>
      <h1>高级模式</h1>
      <p>选择已发布模型，并预设最小推理参数。任务提交会在后续步骤接入。</p>
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
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
    </main>
  );
}
