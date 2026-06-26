import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import {
  listAdminModels,
  publishAdminModel,
  refreshAdminModels,
  uploadAdminOnnxModel,
  type AdminModel,
} from "../../admin-api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Dropzone } from "../../components/ui/dropzone";
import { EmptyState } from "../../components/ui/empty-state";
import { FadeIn } from "../../components/ui/fade-in";
import { Skeleton } from "../../components/ui/skeleton";
import { Badge } from "../../components/ui/badge";

export function ModelsPage() {
  const [models, setModels] = useState<AdminModel[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadModels() {
      try {
        const loaded = await listAdminModels();
        if (!cancelled) setModels(loaded);
      } catch (error) {
        if (!cancelled) setErrorMessage(error instanceof Error ? error.message : "加载模型失败");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void loadModels();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleToggle(model: AdminModel, field: "enabled" | "visible_in_advanced_mode") {
    try {
      const updated = await publishAdminModel(model.id, {
        enabled: field === "enabled" ? !model.enabled : model.enabled,
        visible_in_advanced_mode:
          field === "visible_in_advanced_mode" ? !model.visible_in_advanced_mode : model.visible_in_advanced_mode,
        is_default_person_model: model.is_default_person_model,
      });
      setModels((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "更新模型失败");
    }
  }

  async function handleSetDefault(model: AdminModel) {
    try {
      const updated = await publishAdminModel(model.id, {
        enabled: true,
        visible_in_advanced_mode: model.visible_in_advanced_mode,
        is_default_person_model: true,
      });
      setModels((current) =>
        current.map((item) =>
          item.id === updated.id ? updated : { ...item, is_default_person_model: false },
        ),
      );
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "设置默认模型失败");
    }
  }

  async function handleRefreshModels() {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setErrorMessage(null);
    try {
      setModels(await refreshAdminModels());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "刷新模型目录失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleUploadOnnx(files: File[]) {
    const file = files[0];
    if (!file || isUploading) return;
    setIsUploading(true);
    setErrorMessage(null);
    try {
      const uploaded = await uploadAdminOnnxModel(file);
      setModels((current) => [...current.filter((item) => item.id !== uploaded.id), uploaded]);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "上传 ONNX 失败");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section className="mx-auto grid w-[min(1280px,calc(100%-32px))] gap-5 py-7">
      <FadeIn>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <p className="text-xs font-bold uppercase tracking-wide text-brand">模型管理</p>
            <h1 className="text-3xl font-bold text-ink">模型管理</h1>
            <p className="max-w-2xl text-sm leading-relaxed text-muted">维护已发布模型、默认人检模型与 ONNX 文件。</p>
          </div>
          <Button variant="secondary" size="md" onClick={() => void handleRefreshModels()} disabled={isRefreshing}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            {isRefreshing ? "刷新中..." : "刷新模型目录"}
          </Button>
        </div>
      </FadeIn>

      <FadeIn delay={0.05}>
        <Card>
          <CardHeader>
            <CardTitle>上传 ONNX</CardTitle>
          </CardHeader>
          <CardContent>
            <Dropzone
              accept=".onnx"
              multiple={false}
              disabled={isUploading}
              onFiles={(files) => void handleUploadOnnx(files)}
              hint={isUploading ? "上传中..." : "拖拽 .onnx 文件到此处，或点击选择文件"}
            />
          </CardContent>
        </Card>
      </FadeIn>

      {errorMessage ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{errorMessage}</p>
      ) : null}

      <FadeIn delay={0.1}>
        <Card className="overflow-hidden">
          <div className="grid grid-cols-[2fr_1fr_1fr_1fr_minmax(220px,1.4fr)] gap-3 border-b border-line bg-page px-4 py-3 text-xs font-bold uppercase tracking-wide text-subtle">
            <span>模型</span>
            <span>类型</span>
            <span>状态</span>
            <span>高级模式</span>
            <span>操作</span>
          </div>
          {isLoading ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : models.length === 0 ? (
            <EmptyState title="暂无模型" description="上传 ONNX 文件或刷新模型目录后会显示在这里。" />
          ) : (
            models.map((model) => (
              <div
                key={model.id}
                className="grid grid-cols-[2fr_1fr_1fr_1fr_minmax(220px,1.4fr)] items-center gap-3 border-b border-line px-4 py-3 last:border-b-0"
              >
                <div className="flex flex-col">
                  <span className="font-bold text-ink">{model.name ?? model.slug}</span>
                  <span className="text-xs text-subtle break-all">{model.onnx_path}</span>
                </div>
                <span className="text-sm text-muted">{model.model_kind ?? "—"}</span>
                <Badge variant={model.enabled ? "completed" : "neutral"}>
                  {model.enabled ? "已启用" : "未启用"}
                </Badge>
                <Badge variant={model.visible_in_advanced_mode ? "brand" : "neutral"}>
                  {model.visible_in_advanced_mode ? "可见" : "隐藏"}
                </Badge>
                <div className="flex flex-wrap gap-2">
                  {model.is_default_person_model ? (
                    <Badge variant="completed">默认人检</Badge>
                  ) : model.model_kind === "person_detector" ? (
                    <Button variant="ghost" size="sm" onClick={() => void handleSetDefault(model)}>
                      设为默认人检
                    </Button>
                  ) : null}
                  <Button variant="ghost" size="sm" onClick={() => void handleToggle(model, "enabled")}>
                    {model.enabled ? "停用" : "启用"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => void handleToggle(model, "visible_in_advanced_mode")}>
                    {model.visible_in_advanced_mode ? "隐藏高级" : "发布高级"}
                  </Button>
                </div>
              </div>
            ))
          )}
        </Card>
      </FadeIn>
    </section>
  );
}
