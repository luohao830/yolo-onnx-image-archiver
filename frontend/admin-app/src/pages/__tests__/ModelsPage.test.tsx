import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { listAdminModels, publishAdminModel, refreshAdminModels, uploadAdminOnnxModel } from "../../api/client";
import { ModelsPage } from "../ModelsPage";

vi.mock("../../api/client", () => ({
  listAdminModels: vi.fn(),
  publishAdminModel: vi.fn(),
  refreshAdminModels: vi.fn(),
  uploadAdminOnnxModel: vi.fn()
}));

describe("ModelsPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("lists published models and default person model badge", async () => {
    vi.mocked(listAdminModels).mockResolvedValue([
      {
        id: 1,
        name: "helmet-person-v1",
        slug: "helmet-person-v1",
        onnx_path: "models/helmet-person-v1.onnx",
        sidecar_path: "models/helmet-person-v1.names",
        model_kind: "person_detector",
        enabled: true,
        visible_in_advanced_mode: true,
        is_default_person_model: true
      }
    ]);

    render(<ModelsPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "模型管理" })).toBeTruthy();
      expect(screen.getByText("helmet-person-v1")).toBeTruthy();
      expect(screen.getByText("默认人检模型")).toBeTruthy();
      expect(screen.getByLabelText("上传 ONNX")).toBeTruthy();
      expect(screen.getByRole("button", { name: "刷新模型目录" })).toBeTruthy();
      expect(screen.getByRole("button", { name: "设为默认人检模型" })).toBeTruthy();
    });
  });

  it("can publish a model as the default person model", async () => {
    vi.mocked(listAdminModels).mockResolvedValue([
      {
        id: 2,
        name: "helmet-person-v2",
        slug: "helmet-person-v2",
        onnx_path: "models/helmet-person-v2.onnx",
        sidecar_path: null,
        model_kind: "person_detector",
        enabled: false,
        visible_in_advanced_mode: false,
        is_default_person_model: false
      }
    ]);
    vi.mocked(publishAdminModel).mockResolvedValue({
      id: 2,
      name: "helmet-person-v2",
      slug: "helmet-person-v2",
      onnx_path: "models/helmet-person-v2.onnx",
      sidecar_path: null,
      model_kind: "person_detector",
      enabled: true,
      visible_in_advanced_mode: false,
      is_default_person_model: true
    });

    render(<ModelsPage />);

    await waitFor(() => {
      expect(screen.getByText("helmet-person-v2")).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: "设为默认人检模型" }));

    await waitFor(() => {
      expect(publishAdminModel).toHaveBeenCalledWith(2, {
        enabled: true,
        visible_in_advanced_mode: false,
        is_default_person_model: true
      });
      expect(screen.getByText("默认人检模型")).toBeTruthy();
    });
  });

  it("refreshes models from the mounted models directory", async () => {
    vi.mocked(listAdminModels).mockResolvedValue([]);
    vi.mocked(refreshAdminModels).mockResolvedValue([
      {
        id: 3,
        name: "person",
        slug: "person",
        onnx_path: "/data/models/person.onnx",
        sidecar_path: null,
        model_kind: "person_detector",
        enabled: false,
        visible_in_advanced_mode: false,
        is_default_person_model: false
      }
    ]);

    render(<ModelsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "刷新模型目录" }));

    await waitFor(() => {
      expect(refreshAdminModels).toHaveBeenCalledTimes(1);
      expect(screen.getByText("person")).toBeTruthy();
      expect(screen.getByText("/data/models/person.onnx")).toBeTruthy();
    });
  });

  it("uploads an onnx file and appends the created model", async () => {
    vi.mocked(listAdminModels).mockResolvedValue([]);
    vi.mocked(uploadAdminOnnxModel).mockResolvedValue({
      id: 4,
      name: "uploaded-person",
      slug: "uploaded-person",
      onnx_path: "/data/models/uploaded-person.onnx",
      sidecar_path: null,
      model_kind: "person_detector",
      enabled: false,
      visible_in_advanced_mode: false,
      is_default_person_model: false
    });
    const file = new File(["onnx"], "uploaded-person.onnx", {
      type: "application/octet-stream"
    });

    render(<ModelsPage />);

    fireEvent.change(await screen.findByLabelText("上传 ONNX"), {
      target: {
        files: [file]
      }
    });

    await waitFor(() => {
      expect(uploadAdminOnnxModel).toHaveBeenCalledWith(file);
      expect(screen.getByText("uploaded-person")).toBeTruthy();
      expect(screen.getByText("/data/models/uploaded-person.onnx")).toBeTruthy();
    });
  });
});
