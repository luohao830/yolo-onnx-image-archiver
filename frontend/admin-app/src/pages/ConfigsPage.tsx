import { useEffect, useState } from "react";

import { listAdminConfigs, updateAdminConcurrency } from "../api/client";

export function ConfigsPage() {
  const [taskSlots, setTaskSlots] = useState("3");
  const [gpuSlots, setGpuSlots] = useState("1");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
    try {
      const updated = await updateAdminConcurrency({
        task_slots: Number(taskSlots),
        gpu_slots: Number(gpuSlots)
      });
      setTaskSlots(String(updated.task_slots));
      setGpuSlots(String(updated.gpu_slots));
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "保存系统配置失败");
    }
  }

  return (
    <section>
      <h1>系统配置</h1>
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
      <button type="button" onClick={() => void handleSave()}>
        保存配置
      </button>
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
    </section>
  );
}
