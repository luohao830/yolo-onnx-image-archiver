import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { cancelAdminJob, listAdminJobs, retryAdminJob } from "../../api/client";
import { JobsPage } from "../JobsPage";

vi.mock("../../api/client", () => ({
  listAdminJobs: vi.fn(),
  cancelAdminJob: vi.fn(),
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
        cancel_requested: false,
        error_message: null
      },
      {
        id: 12,
        job_code: "JOB-FAILED",
        mode: "person_filter",
        status: "failed",
        cancel_requested: false,
        error_message: "gpu unavailable"
      }
    ]);
    vi.mocked(cancelAdminJob).mockResolvedValue({
      id: 11,
      job_code: "JOB-RUNNING",
      mode: "advanced",
      status: "running",
      cancel_requested: true,
      error_message: null
    });
    vi.mocked(retryAdminJob).mockResolvedValue({
      id: 12,
      job_code: "JOB-FAILED",
      mode: "person_filter",
      status: "created",
      cancel_requested: false,
      error_message: null
    });

    render(<JobsPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "任务监控" })).toBeTruthy();
      expect(screen.getByText("JOB-RUNNING")).toBeTruthy();
      expect(screen.getByText("JOB-FAILED")).toBeTruthy();
    });

    fireEvent.click(screen.getAllByRole("button", { name: "取消任务" })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: "重试任务" })[0]);

    await waitFor(() => {
      expect(cancelAdminJob).toHaveBeenCalledWith(11);
      expect(retryAdminJob).toHaveBeenCalledWith(12);
      expect(screen.getByText("已请求取消")).toBeTruthy();
      expect(screen.getByText("created")).toBeTruthy();
    });
  });
});
