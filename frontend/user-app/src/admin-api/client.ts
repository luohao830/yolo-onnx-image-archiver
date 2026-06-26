/// <reference types="vite/client" />

import type { JobDetection, JobEvent, JobStats, JobStatus } from "../api/types";

export type { JobStats } from "../api/types";

export interface AdminLoginResponse {
  token: string;
}

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
  status: JobStatus;
  progress: number;
  cancel_requested: boolean;
  error_message: string | null;
  result_zip_available: boolean;
  download_ready: boolean;
}

export type AdminJobEvent = JobEvent;
export type AdminJobDetection = JobDetection;

export interface AdminJobDetail extends AdminJob {
  input_path: string | null;
  result_dir: string | null;
  events: AdminJobEvent[];
  summary?: JobStats | null;
}

export interface AdminJobEventsTokenResponse {
  token: string;
}

export interface AdminJobDetectionsResponse {
  images: AdminJobDetection[];
}

const DEFAULT_API_BASE_URL = "/api";
const ADMIN_TOKEN_KEY = "admin-token";

function resolveApiBaseUrl(): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

  if (!configuredBaseUrl) {
    return DEFAULT_API_BASE_URL;
  }

  return configuredBaseUrl.replace(/\/+$/, "");
}

export async function adminLogin(secret: string): Promise<AdminLoginResponse> {
  const response = await fetch(`${resolveApiBaseUrl()}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ secret })
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `admin login failed: ${response.status}`));
  }

  return response.json() as Promise<AdminLoginResponse>;
}

function getAdminToken(): string {
  return localStorage.getItem(ADMIN_TOKEN_KEY) ?? "";
}

function adminFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  const token = getAdminToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(`${resolveApiBaseUrl()}${path}`, {
    ...init,
    headers
  });
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

export async function issueAdminJobEventsToken(
  jobId: number,
  signal?: AbortSignal,
): Promise<AdminJobEventsTokenResponse> {
  const response = await adminFetch(`/admin/jobs/${jobId}/events-token`, { method: "POST", signal });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `issue admin job events token failed: ${response.status}`));
  }

  return response.json() as Promise<AdminJobEventsTokenResponse>;
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

export function buildAdminJobEventsUrl(jobId: number, sseToken: string): string {
  const params = new URLSearchParams({ sse_token: sseToken });
  return `${resolveApiBaseUrl()}/admin/jobs/${jobId}/events?${params.toString()}`;
}

export function buildAdminJobImageUrl(jobId: number, relPath: string): string {
  return `${resolveApiBaseUrl()}/admin/jobs/${jobId}/images/${encodePath(relPath)}`;
}

const SSE_RECONNECT_DELAY_MS = 3000;

/** 订阅管理员任务 SSE 事件；返回取消订阅函数。 */
export function subscribeAdminJobEvents(
  jobId: number,
  onEvent: (event: AdminJobEvent) => void,
  onError?: (error: Event | Error) => void,
): () => void {
  let closed = false;
  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let tokenRequest: AbortController | null = null;

  const scheduleConnect = (delayMs = 0) => {
    if (closed) return;
    if (delayMs > 0) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        void connect();
      }, delayMs);
      return;
    }
    void connect();
  };

  async function connect() {
    tokenRequest = new AbortController();
    try {
      const { token } = await issueAdminJobEventsToken(jobId, tokenRequest.signal);
      if (closed) return;
      source = new EventSource(buildAdminJobEventsUrl(jobId, token));

      source.onmessage = (messageEvent) => {
        try {
          const parsed: unknown = JSON.parse(messageEvent.data);
          if (isAdminJobEvent(parsed)) onEvent(parsed);
        } catch {
          // 忽略 keepalive 注释与异常帧。
        }
      };

      source.onerror = (event) => {
        if (closed) return;
        onError?.(event);
        source?.close();
        source = null;
        scheduleConnect(SSE_RECONNECT_DELAY_MS);
      };
    } catch (error) {
      if (closed) return;
      onError?.(error instanceof Error ? error : new Event("error"));
      scheduleConnect(SSE_RECONNECT_DELAY_MS);
    } finally {
      tokenRequest = null;
    }
  }

  scheduleConnect();

  return () => {
    closed = true;
    tokenRequest?.abort();
    source?.close();
    if (reconnectTimer) clearTimeout(reconnectTimer);
  };
}

function isAdminJobEvent(value: unknown): value is AdminJobEvent {
  if (typeof value !== "object" || value === null) return false;
  const event = value as Record<string, unknown>;
  return (
    typeof event.id === "number" &&
    typeof event.event_type === "string" &&
    typeof event.message === "string" &&
    typeof event.payload_json === "object" &&
    event.payload_json !== null &&
    !Array.isArray(event.payload_json)
  );
}

export async function getAdminJobDetections(
  jobId: number,
): Promise<AdminJobDetectionsResponse> {
  const response = await adminFetch(`/admin/jobs/${jobId}/detections`);

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `get admin detections failed: ${response.status}`));
  }

  return response.json() as Promise<AdminJobDetectionsResponse>;
}

function encodePath(relPath: string): string {
  return relPath
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
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
