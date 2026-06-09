import { render, screen, waitFor } from "@testing-library/react";
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
});
