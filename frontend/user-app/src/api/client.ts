/// <reference types="vite/client" />

export type JobMode = "person_filter" | "advanced";

export interface CreateJobResponse {
  job_code: string;
  access_token: string;
  status: string;
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
