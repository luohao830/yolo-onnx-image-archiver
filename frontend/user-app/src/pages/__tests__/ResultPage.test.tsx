import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getJobStatus } from "../../api/client";
import { ResultPage } from "../ResultPage";

vi.mock("../../api/client", () => ({
  getJobStatus: vi.fn()
}));

describe("ResultPage", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    cleanup();
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("polls until the job is completed and shows download-ready placeholder", async () => {
    vi.mocked(getJobStatus)
      .mockResolvedValueOnce({
        job_code: "JOB-200",
        mode: "person_filter",
        status: "running"
      })
      .mockResolvedValueOnce({
        job_code: "JOB-200",
        mode: "person_filter",
        status: "completed"
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
      expect(screen.getByText("running")).toBeTruthy();
    });

    await vi.advanceTimersByTimeAsync(2000);

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledTimes(2);
      expect(screen.getByText("completed")).toBeTruthy();
      expect(screen.getByText("结果包已生成，可在后续步骤接入下载按钮。")).toBeTruthy();
    });

    await vi.advanceTimersByTimeAsync(4000);
    expect(getJobStatus).toHaveBeenCalledTimes(2);
  });

  it("shows failed status and error message", async () => {
    vi.mocked(getJobStatus).mockResolvedValue({
      job_code: "JOB-500",
      mode: "advanced",
      status: "failed",
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
    });

    await vi.advanceTimersByTimeAsync(4000);
    expect(getJobStatus).toHaveBeenCalledTimes(1);
  });

  it("stops polling and shows canceled timeline state", async () => {
    vi.mocked(getJobStatus).mockResolvedValue({
      job_code: "JOB-499",
      mode: "person_filter",
      status: "canceled"
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
        status: "running"
      })
      .mockRejectedValueOnce(new Error("network unstable"))
      .mockResolvedValueOnce({
        job_code: "JOB-201",
        mode: "person_filter",
        status: "completed"
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
      expect(screen.getByText("completed")).toBeTruthy();
      expect(screen.queryByRole("alert")).toBeNull();
    });

    await vi.advanceTimersByTimeAsync(4000);
    expect(getJobStatus).toHaveBeenCalledTimes(3);
  });
});
