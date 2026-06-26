import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { listPublishedModels } from "../../api/client";
import { AdvancedModePage } from "../AdvancedModePage";

vi.mock("../../api/client", () => ({
  buildJobDownloadUrl: vi.fn(),
  createAdvancedJob: vi.fn(),
  createJob: vi.fn(),
  getJobStatus: vi.fn(),
  issueJobEventsToken: vi.fn(() => Promise.resolve("events-token")),
  listPublishedModels: vi.fn(),
  subscribeJobEvents: vi.fn(() => () => {}),
  uploadJobFile: vi.fn()
}));

describe("AdvancedModePage", () => {
  it("loads published models for advanced mode", async () => {
    vi.mocked(listPublishedModels).mockResolvedValue([
      {
        id: "helmet-person-v1",
        name: "helmet-person-v1"
      }
    ]);

    render(
      <MemoryRouter>
        <AdvancedModePage />
      </MemoryRouter>,
    );

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
