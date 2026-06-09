import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { listPublishedModels } from "../../api/client";
import { AdvancedModePage } from "../AdvancedModePage";

vi.mock("../../api/client", () => ({
  buildJobDownloadUrl: vi.fn(),
  createJob: vi.fn(),
  getJobStatus: vi.fn(),
  listPublishedModels: vi.fn()
}));

describe("AdvancedModePage", () => {
  it("loads published models for advanced mode", async () => {
    vi.mocked(listPublishedModels).mockResolvedValue([
      {
        id: "helmet-person-v1",
        name: "helmet-person-v1"
      }
    ]);

    render(<AdvancedModePage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "选择模型并查看处理过程" })).toBeTruthy();
      expect(screen.getByText("高级模式")).toBeTruthy();
      expect(screen.getByLabelText("选择模型")).toBeTruthy();
      expect(screen.getByText("helmet-person-v1")).toBeTruthy();
      expect(screen.getByLabelText("置信度阈值")).toBeTruthy();
      expect(screen.getByLabelText("IoU 阈值")).toBeTruthy();
      expect(screen.getByLabelText("批处理大小")).toBeTruthy();
    });
  });
});
