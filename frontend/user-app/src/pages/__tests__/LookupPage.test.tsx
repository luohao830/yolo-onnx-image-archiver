import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LookupPage } from "../LookupPage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LookupPage", () => {
  it("queries job status and shows result", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          job_code: "JOB-100",
          mode: "person_filter",
          status: "running"
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json"
          }
        }
      )
    );

    render(<LookupPage />);

    fireEvent.change(screen.getByLabelText("任务编号"), {
      target: { value: "JOB-100" }
    });
    fireEvent.change(screen.getByLabelText("访问口令"), {
      target: { value: "secret-token" }
    });
    fireEvent.click(screen.getByRole("button", { name: "查询任务" }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/jobs/JOB-100?access_token=secret-token"
      );
      expect(screen.getByText("任务状态")).toBeTruthy();
      expect(screen.getByText("running")).toBeTruthy();
      expect(screen.getByText("任务模式")).toBeTruthy();
      expect(screen.getByText("person_filter")).toBeTruthy();
    });
  });

  it("shows backend error detail when lookup returns 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "job not found" }), {
        status: 404,
        statusText: "Not Found",
        headers: {
          "Content-Type": "application/json"
        }
      })
    );

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
