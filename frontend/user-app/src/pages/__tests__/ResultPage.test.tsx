import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildJobDownloadUrl, getJobDetections, getJobStatus } from "../../api/client";
import { ResultPage } from "../ResultPage";

vi.mock("../../api/client", () => ({
  buildJobDownloadUrl: vi.fn(() => "/api/jobs/JOB-200/download?access_token=token-200"),
  getJobStatus: vi.fn(),
  getJobDetections: vi.fn(),
  issueJobEventsToken: vi.fn(() => Promise.resolve("events-token")),
  subscribeJobEvents: vi.fn(() => () => {}),
  buildJobImageUrl: vi.fn(),
  buildJobEventsUrl: vi.fn()
}));

describe("ResultPage", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(buildJobDownloadUrl).mockImplementation(
      (jobCode: string, accessToken: string) => `/api/jobs/${jobCode}/download?access_token=${accessToken}`
    );
    vi.mocked(getJobDetections).mockResolvedValue({ images: [] });
  });

  afterEach(() => {
    cleanup();
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.resetAllMocks();
  });

  it("polls until the job is completed and shows download-ready placeholder", async () => {
    vi.mocked(getJobStatus)
      .mockResolvedValueOnce({
        job_code: "JOB-200",
        mode: "person_filter",
        status: "running",
        progress: 45,
        download_ready: false,
        events: [
          {
            id: 1,
            event_type: "running",
            message: "正在执行推理处理",
            payload_json: { total: 10, written: 4 }
          }
        ]
      })
      .mockResolvedValueOnce({
        job_code: "JOB-200",
        mode: "person_filter",
        status: "completed",
        progress: 100,
        download_ready: true,
        events: [
          {
            id: 2,
            event_type: "completed",
            message: "输出结果压缩包已生成",
            payload_json: { total: 10, written: 10 }
          }
        ]
      });

    render(
      <MemoryRouter initialEntries={["/results/JOB-200?access_token=token-200"]}>
        <Routes>
          <Route path="/results/:jobCode" element={<ResultPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledWith("JOB-200", "token-200");
      expect(screen.getAllByText("running").length).toBeGreaterThan(0);
      expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("45");
      expect(screen.getByText("正在执行推理处理")).toBeTruthy();
    });

    await vi.advanceTimersByTimeAsync(2000);

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledTimes(2);
      expect(screen.getAllByText("completed").length).toBeGreaterThan(0);
      expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("100");
      expect(screen.getByRole("link", { name: "下载结果压缩包" }).getAttribute("href")).toBe(
        "/api/jobs/JOB-200/download?access_token=token-200"
      );
      expect(buildJobDownloadUrl).toHaveBeenCalledWith("JOB-200", "token-200");
    });

    await vi.advanceTimersByTimeAsync(4000);
    expect(getJobStatus).toHaveBeenCalledTimes(2);
  });

  it("shows failed status and error message", async () => {
    vi.mocked(getJobStatus).mockResolvedValue({
      job_code: "JOB-500",
      mode: "advanced",
      status: "failed",
      progress: 60,
      download_ready: false,
      events: [],
      error_message: "模型推理失败"
    });

    render(
      <MemoryRouter initialEntries={["/results/JOB-500?access_token=token-500"]}>
        <Routes>
          <Route path="/results/:jobCode" element={<ResultPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledWith("JOB-500", "token-500");
      expect(screen.getByText("failed")).toBeTruthy();
      expect(screen.getByRole("alert").textContent).toBe("模型推理失败");
      expect(screen.queryByRole("link", { name: "下载结果压缩包" })).toBeNull();
    });

    await vi.advanceTimersByTimeAsync(4000);
    expect(getJobStatus).toHaveBeenCalledTimes(1);
  });

  it("stops polling and shows canceled timeline state", async () => {
    vi.mocked(getJobStatus).mockResolvedValue({
      job_code: "JOB-499",
      mode: "person_filter",
      status: "canceled",
      progress: 0,
      download_ready: false,
      events: []
    });

    render(
      <MemoryRouter initialEntries={["/results/JOB-499?access_token=token-499"]}>
        <Routes>
          <Route path="/results/:jobCode" element={<ResultPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledWith("JOB-499", "token-499");
      expect(screen.getByText("canceled")).toBeTruthy();
      expect(screen.getByText("任务已取消")).toBeTruthy();
    });

    await vi.advanceTimersByTimeAsync(4000);
    expect(getJobStatus).toHaveBeenCalledTimes(1);
  });

  it("keeps polling after a transient error and eventually stops at completed", async () => {
    vi.mocked(getJobStatus)
      .mockResolvedValueOnce({
        job_code: "JOB-201",
        mode: "person_filter",
        status: "running",
        progress: 45,
        download_ready: false,
        events: []
      })
      .mockRejectedValueOnce(new Error("network unstable"))
      .mockResolvedValueOnce({
        job_code: "JOB-201",
        mode: "person_filter",
        status: "completed",
        progress: 100,
        download_ready: true,
        events: []
      });

    render(
      <MemoryRouter initialEntries={["/results/JOB-201?access_token=token-201"]}>
        <Routes>
          <Route path="/results/:jobCode" element={<ResultPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledWith("JOB-201", "token-201");
      expect(screen.getByText("running")).toBeTruthy();
    });

    await vi.advanceTimersByTimeAsync(2000);

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledTimes(2);
      expect(screen.getByRole("alert").textContent).toBe("network unstable");
      expect(screen.getByText("running")).toBeTruthy();
    });

    await vi.advanceTimersByTimeAsync(2000);

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledTimes(3);
      expect(screen.getAllByText("completed").length).toBeGreaterThan(0);
      expect(screen.queryByRole("alert")).toBeNull();
    });

    await vi.advanceTimersByTimeAsync(4000);
    expect(getJobStatus).toHaveBeenCalledTimes(3);
  });
});
