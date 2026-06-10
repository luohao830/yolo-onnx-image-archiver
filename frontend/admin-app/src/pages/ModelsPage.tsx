import { useEffect, useState } from "react";

import {
  listAdminModels,
  publishAdminModel,
  refreshAdminModels,
  uploadAdminOnnxModel,
  type AdminModel
} from "../api/client";

export function ModelsPage() {
  const [models, setModels] = useState<AdminModel[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadModels() {
      try {
        const loaded = await listAdminModels();
        if (!cancelled) {
          setModels(loaded);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "加载模型失败");
        }
      }
    }

    void loadModels();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSetDefault(model: AdminModel) {
    const updated = await publishAdminModel(model.id, {
      enabled: model.enabled,
      visible_in_advanced_mode: model.visible_in_advanced_mode,
      is_default_person_model: true
    });

    setModels((current) =>
      current.map((item) =>
        item.id === updated.id
          ? updated
          : {
              ...item,
              is_default_person_model: false
            }
      )
    );
  }

  async function handleRefreshModels() {
    if (isRefreshing) {
      return;
    }

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

  async function handleUploadOnnx(file: File | null) {
    if (!file || isUploading) {
      return;
    }

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
    <section>
      <h1>模型管理</h1>
      <p>维护已发布模型、默认人检模型和 sidecar 文件。</p>
      <div>
        <label htmlFor="onnx-upload">上传 ONNX</label>
        <input
          id="onnx-upload"
          type="file"
          accept=".onnx"
          disabled={isUploading}
          onChange={(event) => void handleUploadOnnx(event.target.files?.[0] ?? null)}
        />
        <button type="button" onClick={() => void handleRefreshModels()} disabled={isRefreshing}>
          {isRefreshing ? "刷新中..." : "刷新模型目录"}
        </button>
      </div>
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      <ul>
        {models.map((model) => (
          <li key={model.id}>
            <strong>{model.name}</strong>
            <span>{model.onnx_path}</span>
            {model.is_default_person_model ? <span>默认人检模型</span> : null}
            <button type="button" onClick={() => void handleSetDefault(model)}>
              设为默认人检模型
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
