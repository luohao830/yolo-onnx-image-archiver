import { useEffect, useState } from "react";

import { listAdminConfigs, updateAdminConcurrency } from "../../admin-api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { FadeIn } from "../../components/ui/fade-in";

function validateSlots(value: string, label: string): string | null {
  const num = Number(value);
  if (Number.isNaN(num) || !Number.isInteger(num) || num < 1 || num > 3) {
    return `${label}需为 1-3 之间的整数`;
  }
  return null;
}

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
        if (!cancelled) setErrorMessage(error instanceof Error ? error.message : "加载系统配置失败");
      }
    }
    void loadConfigs();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    if (isSaving) return;
    const taskErr = validateSlots(taskSlots, "任务处理器并发数");
    const gpuErr = validateSlots(gpuSlots, "GPU 推理并发数");
    if (taskErr || gpuErr) {
      setErrorMessage(taskErr ?? gpuErr);
      setSaveMessage(null);
      return;
    }
    setIsSaving(true);
    setErrorMessage(null);
    setSaveMessage(null);
    try {
      const updated = await updateAdminConcurrency({
        task_slots: Number(taskSlots),
        gpu_slots: Number(gpuSlots),
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
    <section className="mx-auto grid w-[min(1280px,calc(100%-32px))] gap-5 py-7">
      <FadeIn>
        <div className="space-y-1">
          <p className="text-xs font-bold uppercase tracking-wide text-brand">系统配置</p>
          <h1 className="text-3xl font-bold text-ink">单机并发配置</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted">
            调整任务队列和 GPU 推理并发数。内网单机版建议保持 GPU 并发为 1，优先保障稳定性。
          </p>
        </div>
      </FadeIn>

      <FadeIn delay={0.05}>
        <Card>
          <CardHeader>
            <CardTitle>并发参数</CardTitle>
            <CardDescription>任务处理器并发数与 GPU 推理并发数均限制在 1-3。</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div className="grid gap-4 sm:grid-cols-[200px_minmax(0,1fr)] sm:items-center">
              <label htmlFor="task-slots" className="text-sm font-bold text-ink">任务处理器并发数</label>
              <input
                id="task-slots"
                type="number"
                min={1}
                max={3}
                value={taskSlots}
                onChange={(event) => setTaskSlots(event.target.value)}
                className="w-full rounded-md border border-line-strong bg-card px-3 py-2.5 text-ink"
              />
              <label htmlFor="gpu-slots" className="text-sm font-bold text-ink">GPU 推理并发数</label>
              <input
                id="gpu-slots"
                type="number"
                min={1}
                max={3}
                value={gpuSlots}
                onChange={(event) => setGpuSlots(event.target.value)}
                className="w-full rounded-md border border-line-strong bg-card px-3 py-2.5 text-ink"
              />
            </div>
            <Button variant="primary" size="md" className="self-start" disabled={isSaving} onClick={() => void handleSave()}>
              {isSaving ? "保存中..." : "保存配置"}
            </Button>
          </CardContent>
        </Card>
      </FadeIn>

      {errorMessage ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{errorMessage}</p>
      ) : null}
      {saveMessage ? (
        <p className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700" role="status">{saveMessage}</p>
      ) : null}
    </section>
  );
}
