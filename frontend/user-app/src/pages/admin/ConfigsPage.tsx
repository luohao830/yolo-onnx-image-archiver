import { useEffect, useState } from "react";

import { listAdminConfigs, updateAdminConcurrency } from "../../admin-api/client";

export function ConfigsPage() {
  const [taskSlots, setTaskSlots] = useState("3");
  const [gpuSlots, setGpuSlots] = useState("1");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadConfigs() {
      try {
        const configs = await listAdminConfigs();

        if (!cancelled) {
          setTaskSlots(String(configs.task_slots));
          setGpuSlots(String(configs.gpu_slots));
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "加载系统配置失败");
        }
      }
    }

    void loadConfigs();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    if (isSaving) {
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    setSaveMessage(null);

    try {
      const updated = await updateAdminConcurrency({
        task_slots: Number(taskSlots),
        gpu_slots: Number(gpuSlots)
      });
      setTaskSlots(String(updated.task_slots));
      setGpuSlots(String(updated.gpu_slots));
      setSaveMessage("配置已保存");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "保存系统配置失败");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="admin-page">
      <div className="page-heading">
        <p className="eyebrow">系统配置</p>
        <h1>单机并发配置</h1>
        <p>调整任务队列和 GPU 推理并发数。内网单机版建议保持 GPU 并发为 1，优先保障稳定性。</p>
      </div>

      <section className="work-card admin-form-card" aria-label="系统配置表单">
        <div className="form-grid">
          <label htmlFor="task-slots">任务处理器并发数</label>
          <input
            id="task-slots"
            type="number"
            min="1"
            max="3"
            value={taskSlots}
            onChange={(event) => setTaskSlots(event.target.value)}
          />
          <label htmlFor="gpu-slots">GPU 推理并发数</label>
          <input
            id="gpu-slots"
            type="number"
            min="1"
            max="3"
            value={gpuSlots}
            onChange={(event) => setGpuSlots(event.target.value)}
          />
        </div>
        <button className="button button--primary" type="button" onClick={() => void handleSave()} disabled={isSaving}>
          {isSaving ? "保存中..." : "保存配置"}
        </button>
      </section>

      {errorMessage ? <p className="alert" role="alert">{errorMessage}</p> : null}
      {saveMessage ? <p className="notice" role="status">{saveMessage}</p> : null}
    </section>
  );
}
