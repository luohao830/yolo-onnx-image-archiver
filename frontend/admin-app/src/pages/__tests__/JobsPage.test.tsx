import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  cancelAdminJob,
  downloadAdminJobResult,
  getAdminJob,
  listAdminJobs,
  retryAdminJob
} from "../../api/client";
import { JobsPage } from "../JobsPage";

vi.mock("../../api/client", () => ({
  cancelAdminJob: vi.fn(),
  downloadAdminJobResult: vi.fn(),
  getAdminJob: vi.fn(),
  listAdminJobs: vi.fn(),
  retryAdminJob: vi.fn()
}));

describe("JobsPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("lists admin jobs and supports cancel plus retry actions", async () => {
    vi.mocked(listAdminJobs).mockResolvedValue([
      {
        id: 11,
        job_code: "JOB-RUNNING",
        mode: "advanced",
        status: "running",
        progress: 72,
        cancel_requested: false,
        error_message: null,
        result_zip_available: false,
        download_ready: false
      },
      {
        id: 12,
        job_code: "JOB-FAILED",
        mode: "person_filter",
        status: "failed",
        progress: 44,
        cancel_requested: false,
        error_message: "gpu unavailable",
        result_zip_available: false,
        download_ready: false
      },
      {
        id: 13,
        job_code: "JOB-DONE",
        mode: "person_filter",
        status: "completed",
        progress: 100,
        cancel_requested: false,
        error_message: null,
        result_zip_available: true,
        download_ready: true
      }
    ]);
    vi.mocked(getAdminJob).mockResolvedValue({
      id: 13,
      job_code: "JOB-DONE",
      mode: "person_filter",
      status: "completed",
      progress: 100,
      cancel_requested: false,
      error_message: null,
      input_path: "/runtime/uploads/JOB-DONE",
      result_dir: "/runtime/results/JOB-DONE",
      result_zip_available: true,
      download_ready: true,
      events: [
        {
          id: 1,
          event_type: "completed",
          message: "输出结果压缩包已生成",
          payload_json: {
            total: 2,
            written: 2
          }
        }
      ]
    });
    vi.mocked(downloadAdminJobResult).mockResolvedValue(undefined);
    vi.mocked(cancelAdminJob).mockResolvedValue({
      id: 11,
      job_code: "JOB-RUNNING",
      mode: "advanced",
      status: "running",
      progress: 72,
      cancel_requested: true,
      error_message: null,
      result_zip_available: false,
      download_ready: false
    });
    vi.mocked(retryAdminJob).mockResolvedValue({
      id: 12,
      job_code: "JOB-FAILED",
      mode: "person_filter",
      status: "created",
      progress: 5,
      cancel_requested: false,
      error_message: null,
      result_zip_available: false,
      download_ready: false
    });

    render(<JobsPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "任务监控" })).toBeTruthy();
      expect(screen.getByText("JOB-RUNNING")).toBeTruthy();
      expect(screen.getByText("JOB-FAILED")).toBeTruthy();
      expect(screen.getByText("72%")).toBeTruthy();
      expect(screen.getByText("100%")).toBeTruthy();
    });

    fireEvent.click(screen.getAllByRole("button", { name: "取消任务" })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: "重试任务" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "查看 JOB-DONE 详情" }));

    await waitFor(() => {
      expect(cancelAdminJob).toHaveBeenCalledWith(11);
      expect(retryAdminJob).toHaveBeenCalledWith(12);
      expect(getAdminJob).toHaveBeenCalledWith(13);
      expect(screen.getByText("已请求取消")).toBeTruthy();
      expect(screen.getByText("created")).toBeTruthy();
      expect(screen.getByText("输出结果压缩包已生成")).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: "下载输出结果" }));

    await waitFor(() => {
      expect(downloadAdminJobResult).toHaveBeenCalledWith(13);
    });
  });
});
