/// <reference types="vite/client" />

export type JobMode = "person_filter" | "advanced";
export type JobStatus = "created" | "uploaded" | "running" | "completed" | "failed";

export interface CreateJobResponse {
  job_code: string;
  access_token: string;
  status: string;
}

export interface PublishedModel {
  id: string;
  name: string;
}

export interface PublicJobStatus {
  job_code: string;
  mode: JobMode;
  status: JobStatus;
  error_message?: string | null;
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
