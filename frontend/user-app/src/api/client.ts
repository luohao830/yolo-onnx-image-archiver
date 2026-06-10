/// <reference types="vite/client" />

export type JobMode = "person_filter" | "advanced";
export type JobStatus = "created" | "uploaded" | "running" | "completed" | "failed" | "canceled";

export interface CreateJobResponse {
  job_code: string;
  access_token: string;
  status: string;
}

export interface JobEvent {
  id: number;
  event_type: string;
  message: string;
  payload_json: Record<string, unknown>;
}

export interface PublishedModel {
  id: string;
  name: string;
}

export interface PublicJobStatus {
  job_code: string;
  mode: JobMode;
  status: JobStatus;
  progress: number;
  events: JobEvent[];
  error_message?: string | null;
  download_ready: boolean;
}

export interface UploadJobFileOptions {
  contentSha256?: string;
  onProgress?: (progress: number) => void;
}

const DEFAULT_API_BASE_URL = "/api";

function resolveApiBaseUrl(): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

  if (!configuredBaseUrl) {
    return DEFAULT_API_BASE_URL;
  }

  return configuredBaseUrl.replace(/\/+$/, "");
}

export async function createJob(mode: JobMode): Promise<CreateJobResponse> {
  const response = await fetch(`${resolveApiBaseUrl()}/jobs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ mode })
  });

  if (!response.ok) {
    throw new Error(`create job failed: ${response.status}`);
  }

  return response.json() as Promise<CreateJobResponse>;
}

export async function listPublishedModels(): Promise<PublishedModel[]> {
  const response = await fetch(`${resolveApiBaseUrl()}/jobs/models`);

  if (!response.ok) {
    throw new Error(`list models failed: ${response.status}`);
  }

  return response.json() as Promise<PublishedModel[]>;
}

export async function getJobStatus(
  jobCode: string,
  accessToken: string
): Promise<PublicJobStatus> {
  const searchParams = new URLSearchParams({
    access_token: accessToken
  });
  const response = await fetch(
    `${resolveApiBaseUrl()}/jobs/${encodeURIComponent(jobCode)}?${searchParams.toString()}`
  );

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `get job status failed: ${response.status}`));
  }

  return response.json() as Promise<PublicJobStatus>;
}

export async function uploadJobFile(
  jobCode: string,
  accessToken: string,
  file: File,
  options: UploadJobFileOptions = {}
): Promise<PublicJobStatus> {
  const searchParams = new URLSearchParams({
    access_token: accessToken
  });
  const formData = new FormData();
  formData.append("file", file);
  if (options.contentSha256) {
    formData.append("content_sha256", options.contentSha256);
  }

  return sendUploadRequest(
    `${resolveApiBaseUrl()}/jobs/${encodeURIComponent(jobCode)}/upload?${searchParams.toString()}`,
    formData,
    options.onProgress
  );
}

export async function reuseUploadedArchive(
  jobCode: string,
  accessToken: string,
  contentSha256: string
): Promise<PublicJobStatus | null> {
  const searchParams = new URLSearchParams({
    access_token: accessToken
  });
  const response = await fetch(
    `${resolveApiBaseUrl()}/jobs/${encodeURIComponent(jobCode)}/reuse-upload?${searchParams.toString()}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ content_sha256: contentSha256 })
    }
  );

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `reuse uploaded archive failed: ${response.status}`));
  }

  return response.json() as Promise<PublicJobStatus>;
}

export async function calculateFileSha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function buildJobDownloadUrl(jobCode: string, accessToken: string): string {
  const searchParams = new URLSearchParams({
    access_token: accessToken
  });

  return `${resolveApiBaseUrl()}/jobs/${encodeURIComponent(jobCode)}/download?${searchParams.toString()}`;
}

async function readErrorMessage(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    // Ignore non-JSON error bodies and fall back to status text below.
  }

  return response.statusText || fallbackMessage;
}

function sendUploadRequest(
  url: string,
  formData: FormData,
  onProgress?: (progress: number) => void
): Promise<PublicJobStatus> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);

    request.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) {
        return;
      }
      onProgress(Math.max(0, Math.min(100, Math.round((event.loaded / event.total) * 100))));
    };

    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(JSON.parse(request.responseText) as PublicJobStatus);
        return;
      }

      reject(new Error(readXhrErrorMessage(request, `upload job file failed: ${request.status}`)));
    };
    request.onerror = () => reject(new Error("上传文件失败"));
    request.send(formData);
  });
}

function readXhrErrorMessage(request: XMLHttpRequest, fallbackMessage: string): string {
  try {
    const payload = JSON.parse(request.responseText) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    // Ignore non-JSON error bodies and fall back to the default message.
  }

  return request.statusText || fallbackMessage;
}
