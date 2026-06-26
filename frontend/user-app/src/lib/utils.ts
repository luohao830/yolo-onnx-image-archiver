import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { JobStatus } from "../api/types";

/** 合并 Tailwind class，解决冲突并支持条件类名。 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatSeconds(value?: number | null): string {
  if (value === undefined || value === null) return "—";
  if (value < 1) return `${(value * 1000).toFixed(0)} ms`;
  return `${value.toFixed(2)} s`;
}

export function isTerminalStatus(status: JobStatus): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}

export function clampProgress(progress: number): number {
  return Math.max(0, Math.min(100, Math.round(progress)));
}

export function getFallbackProgress(status: JobStatus): number {
  const values: Record<JobStatus, number> = {
    created: 0,
    uploaded: 10,
    running: 0,
    completed: 100,
    failed: 0,
    canceled: 0,
  };
  return values[status];
}
