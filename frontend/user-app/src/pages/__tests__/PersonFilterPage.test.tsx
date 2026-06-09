import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createJob } from "../../api/client";
import { PersonFilterPage } from "../PersonFilterPage";


vi.mock("../../api/client", () => ({
  createJob: vi.fn()
}));

describe("PersonFilterPage", () => {
  it("submits person filter job and shows receipt", async () => {
    vi.mocked(createJob).mockResolvedValue({
      job_code: "JOB-123456",
      access_token: "token-123",
      status: "created"
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
      expect(screen.getByText("任务编号")).toBeTruthy();
      expect(screen.getByText("JOB-123456")).toBeTruthy();
      expect(screen.getByText("访问口令")).toBeTruthy();
      expect(screen.getByText("token-123")).toBeTruthy();
    });
  });
});
