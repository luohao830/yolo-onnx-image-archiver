import { useEffect, useState } from "react";

import { listAdminModels, publishAdminModel, type AdminModel } from "../api/client";

export function ModelsPage() {
  const [models, setModels] = useState<AdminModel[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  return (
    <section>
      <h1>模型管理</h1>
      <p>维护已发布模型、默认人检模型和 sidecar 文件。</p>
      <button type="button">上传 ONNX</button>
      <button type="button">上传 sidecar</button>
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      <ul>
        {models.map((model) => (
          <li key={model.id}>
            <strong>{model.name}</strong>
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
