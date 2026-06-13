/// <reference types="vite/client" />

export interface AdminModel {
  id: number;
  name: string;
  slug: string;
  onnx_path: string;
  sidecar_path: string | null;
  model_kind: string;
  enabled: boolean;
  visible_in_advanced_mode: boolean;
  is_default_person_model: boolean;
}

export interface PublishAdminModelPayload {
  enabled: boolean;
  visible_in_advanced_mode: boolean;
  is_default_person_model: boolean;
}

export interface AdminConfig {
  task_slots: number;
  gpu_slots: number;
}

export interface AdminJob {
  id: number;
  job_code: string;
  mode: string;
  status: string;
  progress: number;
  cancel_requested: boolean;
  error_message: string | null;
  result_zip_available: boolean;
  download_ready: boolean;
}

export interface AdminJobEvent {
  id: number;
  event_type: string;
  message: string;
  payload_json: Record<string, unknown>;
}

export interface AdminJobDetail extends AdminJob {
  input_path: string | null;
  result_dir: string | null;
  events: AdminJobEvent[];
}

const DEFAULT_API_BASE_URL = "/api";

function resolveApiBaseUrl(): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

  if (!configuredBaseUrl) {
    return DEFAULT_API_BASE_URL;
  }

  return configuredBaseUrl.replace(/\/+$/, "");
}

function adminFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${resolveApiBaseUrl()}${path}`, init);
}

export async function listAdminModels(): Promise<AdminModel[]> {
  const response = await adminFetch("/admin/models");

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `list admin models failed: ${response.status}`));
  }

  return response.json() as Promise<AdminModel[]>;
}

export async function refreshAdminModels(): Promise<AdminModel[]> {
  const response = await adminFetch("/admin/models/refresh", { method: "POST" });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `refresh admin models failed: ${response.status}`));
  }

  return response.json() as Promise<AdminModel[]>;
}

export async function uploadAdminOnnxModel(file: File): Promise<AdminModel> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await adminFetch("/admin/models/upload", {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `upload admin model failed: ${response.status}`));
  }

  return response.json() as Promise<AdminModel>;
}

export async function publishAdminModel(
  modelId: number,
  payload: PublishAdminModelPayload
): Promise<AdminModel> {
  const response = await adminFetch(`/admin/models/${modelId}/publish`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `publish admin model failed: ${response.status}`));
  }

  return response.json() as Promise<AdminModel>;
}

export async function listAdminConfigs(): Promise<AdminConfig> {
  const response = await adminFetch("/admin/configs");

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `list admin configs failed: ${response.status}`));
  }

  return response.json() as Promise<AdminConfig>;
}

export async function updateAdminConcurrency(payload: AdminConfig): Promise<AdminConfig> {
  const response = await adminFetch("/admin/configs/concurrency", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `update admin configs failed: ${response.status}`));
  }

  return response.json() as Promise<AdminConfig>;
}

export async function listAdminJobs(): Promise<AdminJob[]> {
  const response = await adminFetch("/admin/jobs");

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `list admin jobs failed: ${response.status}`));
  }

  return response.json() as Promise<AdminJob[]>;
}

export async function getAdminJob(jobId: number): Promise<AdminJobDetail> {
  const response = await adminFetch(`/admin/jobs/${jobId}`);

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `get admin job failed: ${response.status}`));
  }

  return response.json() as Promise<AdminJobDetail>;
}

export async function cancelAdminJob(jobId: number): Promise<AdminJob> {
  const response = await adminFetch(`/admin/jobs/${jobId}/cancel`, { method: "POST" });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `cancel admin job failed: ${response.status}`));
  }

  return response.json() as Promise<AdminJob>;
}

export async function retryAdminJob(jobId: number): Promise<AdminJob> {
  const response = await adminFetch(`/admin/jobs/${jobId}/retry`, { method: "POST" });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `retry admin job failed: ${response.status}`));
  }

  return response.json() as Promise<AdminJob>;
}

export async function downloadAdminJobResult(jobId: number): Promise<void> {
  const response = await adminFetch(`/admin/jobs/${jobId}/download`);

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `download admin job result failed: ${response.status}`));
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `job-${jobId}.zip`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function readErrorMessage(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    // Ignore non-JSON error bodies and fall back to the default message.
  }

  return response.statusText || fallbackMessage;
}
