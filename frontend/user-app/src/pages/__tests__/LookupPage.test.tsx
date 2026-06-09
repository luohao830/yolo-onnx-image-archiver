import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getJobStatus } from "../../api/client";
import { LookupPage } from "../LookupPage";

vi.mock("../../api/client", () => ({
  getJobStatus: vi.fn()
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LookupPage", () => {
  it("queries job status and shows result", async () => {
    vi.mocked(getJobStatus).mockResolvedValue({
      job_code: "JOB-100",
      mode: "person_filter",
      status: "running"
    });

    render(<LookupPage />);

    fireEvent.change(screen.getByLabelText("任务编号"), {
      target: { value: "JOB-100" }
    });
    fireEvent.change(screen.getByLabelText("访问口令"), {
      target: { value: "secret-token" }
    });
    fireEvent.click(screen.getByRole("button", { name: "查询任务" }));

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledWith("JOB-100", "secret-token");
      expect(screen.getByText("任务状态")).toBeTruthy();
      expect(screen.getByText("running")).toBeTruthy();
      expect(screen.getByText("任务模式")).toBeTruthy();
      expect(screen.getByText("person_filter")).toBeTruthy();
    });
  });

  it("shows an error message when lookup fails", async () => {
    vi.mocked(getJobStatus).mockRejectedValue(new Error("job not found"));

    render(<LookupPage />);

    fireEvent.change(screen.getByLabelText("任务编号"), {
      target: { value: "JOB-404" }
    });
    fireEvent.change(screen.getByLabelText("访问口令"), {
      target: { value: "bad-token" }
    });
    fireEvent.click(screen.getByRole("button", { name: "查询任务" }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toBe("job not found");
    });
  });
});
