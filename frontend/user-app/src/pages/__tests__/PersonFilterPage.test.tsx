import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { buildJobDownloadUrl, createJob, getJobStatus } from "../../api/client";
import { PersonFilterPage } from "../PersonFilterPage";


vi.mock("../../api/client", () => ({
  buildJobDownloadUrl: vi.fn(() => "/api/jobs/JOB-123456/download?access_token=token-123"),
  createJob: vi.fn(),
  getJobStatus: vi.fn()
}));

describe("PersonFilterPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("submits person filter job and shows progress logs without exposing credentials", async () => {
    vi.mocked(createJob).mockResolvedValue({
      job_code: "JOB-123456",
      access_token: "token-123",
      status: "created"
    });
    vi.mocked(getJobStatus).mockResolvedValue({
      job_code: "JOB-123456",
      mode: "person_filter",
      status: "completed",
      progress: 100,
      download_ready: true,
      events: [
        {
          id: 1,
          event_type: "completed",
          message: "输出结果压缩包已生成",
          payload_json: {
            total: 10,
            written: 10
          }
        }
      ]
    });

    render(<PersonFilterPage />);

    fireEvent.change(screen.getByLabelText("上传图片或压缩包"), {
      target: {
        files: [new File(["demo"], "images.zip", { type: "application/zip" })]
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "开始处理" }));

    await waitFor(() => {
      expect(createJob).toHaveBeenCalledWith("person_filter");
      expect(getJobStatus).toHaveBeenCalledWith("JOB-123456", "token-123");
      expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("100");
      expect(screen.getByText("输出结果压缩包已生成")).toBeTruthy();
      expect(screen.getByRole("link", { name: "下载结果压缩包" }).getAttribute("href")).toBe(
        "/api/jobs/JOB-123456/download?access_token=token-123"
      );
      expect(buildJobDownloadUrl).toHaveBeenCalledWith("JOB-123456", "token-123");
    });

    expect(screen.queryByText("JOB-123456")).toBeNull();
    expect(screen.queryByText("token-123")).toBeNull();
  });
});
