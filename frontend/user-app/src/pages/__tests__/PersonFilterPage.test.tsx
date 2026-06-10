import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildJobDownloadUrl,
  calculateFileSha256,
  createJob,
  getJobStatus,
  reuseUploadedArchive,
  uploadJobFile
} from "../../api/client";
import { PersonFilterPage } from "../PersonFilterPage";


vi.mock("../../api/client", () => ({
  buildJobDownloadUrl: vi.fn(() => "/api/jobs/JOB-123456/download?access_token=token-123"),
  calculateFileSha256: vi.fn(),
  createJob: vi.fn(),
  getJobStatus: vi.fn(),
  reuseUploadedArchive: vi.fn(),
  uploadJobFile: vi.fn()
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
    vi.mocked(calculateFileSha256).mockResolvedValue("zip-sha-256");
    vi.mocked(reuseUploadedArchive).mockResolvedValue(null);
    vi.mocked(uploadJobFile).mockImplementation(async (_jobCode, _accessToken, _file, options) => {
      options?.onProgress?.(37);
      return {
      job_code: "JOB-123456",
      mode: "person_filter",
      status: "uploaded",
      progress: 100,
      download_ready: false,
      events: [
        {
          id: 1,
          event_type: "uploaded",
          message: "文件已接收，任务已进入队列",
          payload_json: {
            total: 1
          }
        }
      ]
      };
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

    const file = new File(["demo"], "images.zip", { type: "application/zip" });
    fireEvent.change(screen.getByLabelText("上传图片或压缩包"), {
      target: {
        files: [file]
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "开始处理" }));

    await waitFor(() => {
      expect(createJob).toHaveBeenCalledWith("person_filter");
      expect(calculateFileSha256).toHaveBeenCalledWith(file);
      expect(reuseUploadedArchive).toHaveBeenCalledWith("JOB-123456", "token-123", "zip-sha-256");
      expect(uploadJobFile).toHaveBeenCalledWith(
        "JOB-123456",
        "token-123",
        file,
        expect.objectContaining({ contentSha256: "zip-sha-256" })
      );
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

  it("reuses an uploaded archive when the precomputed hash is already cached", async () => {
    vi.mocked(createJob).mockResolvedValue({
      job_code: "JOB-CACHED",
      access_token: "token-cached",
      status: "created"
    });
    vi.mocked(calculateFileSha256).mockResolvedValue("cached-sha-256");
    vi.mocked(reuseUploadedArchive).mockResolvedValue({
      job_code: "JOB-CACHED",
      mode: "person_filter",
      status: "uploaded",
      progress: 100,
      download_ready: false,
      events: [
        {
          id: 1,
          event_type: "uploaded",
          message: "已复用上传压缩包，任务已进入队列",
          payload_json: { reused: true }
        }
      ]
    });
    vi.mocked(getJobStatus).mockResolvedValue({
      job_code: "JOB-CACHED",
      mode: "person_filter",
      status: "running",
      progress: 12,
      download_ready: false,
      events: []
    });

    render(<PersonFilterPage />);

    const file = new File(["demo"], "images.zip", { type: "application/zip" });
    fireEvent.change(screen.getByLabelText("上传图片或压缩包"), {
      target: {
        files: [file]
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "开始处理" }));

    await waitFor(() => {
      expect(calculateFileSha256).toHaveBeenCalledWith(file);
      expect(reuseUploadedArchive).toHaveBeenCalledWith("JOB-CACHED", "token-cached", "cached-sha-256");
      expect(uploadJobFile).not.toHaveBeenCalled();
      expect(getJobStatus).toHaveBeenCalledWith("JOB-CACHED", "token-cached");
    });
  });

  it("skips pre-upload hash reuse for oversized zip files", async () => {
    vi.mocked(createJob).mockResolvedValue({
      job_code: "JOB-LARGE",
      access_token: "token-large",
      status: "created"
    });
    vi.mocked(uploadJobFile).mockResolvedValue({
      job_code: "JOB-LARGE",
      mode: "person_filter",
      status: "uploaded",
      progress: 100,
      download_ready: false,
      events: []
    });
    vi.mocked(getJobStatus).mockResolvedValue({
      job_code: "JOB-LARGE",
      mode: "person_filter",
      status: "running",
      progress: 0,
      download_ready: false,
      events: []
    });

    render(<PersonFilterPage />);

    const file = new File(["demo"], "large.zip", { type: "application/zip" });
    Object.defineProperty(file, "size", {
      value: 1024 * 1024 * 1024
    });
    fireEvent.change(screen.getByLabelText("上传图片或压缩包"), {
      target: {
        files: [file]
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "开始处理" }));

    await waitFor(() => {
      expect(calculateFileSha256).not.toHaveBeenCalled();
      expect(reuseUploadedArchive).not.toHaveBeenCalled();
      expect(uploadJobFile).toHaveBeenCalledWith(
        "JOB-LARGE",
        "token-large",
        file,
        expect.objectContaining({ contentSha256: undefined })
      );
    });
  });
});
