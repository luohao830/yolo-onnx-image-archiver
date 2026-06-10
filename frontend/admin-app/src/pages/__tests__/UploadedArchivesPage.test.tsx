import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteUploadedArchives, listUploadedArchives } from "../../api/client";
import { UploadedArchivesPage } from "../UploadedArchivesPage";

vi.mock("../../api/client", () => ({
  deleteUploadedArchives: vi.fn(),
  listUploadedArchives: vi.fn()
}));

describe("UploadedArchivesPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("lists uploaded archives and deletes selected rows", async () => {
    vi.mocked(listUploadedArchives)
      .mockResolvedValueOnce([
        {
          id: 7,
          content_sha256: "abcdef123456",
          original_filename: "images.zip",
          size_bytes: 1024,
          image_count: 2,
          created_at: "2026-06-10T12:00:00Z"
        }
      ])
      .mockResolvedValueOnce([]);
    vi.mocked(deleteUploadedArchives).mockResolvedValue({ deleted: 1 });

    render(<UploadedArchivesPage />);

    await waitFor(() => {
      expect(screen.getByText("images.zip")).toBeTruthy();
      expect(screen.getByText("2")).toBeTruthy();
    });

    fireEvent.click(screen.getByLabelText("选择 images.zip"));
    fireEvent.click(screen.getByRole("button", { name: "删除选中压缩包" }));

    await waitFor(() => {
      expect(deleteUploadedArchives).toHaveBeenCalledWith([7]);
      expect(screen.getByText("暂无已上传压缩包。")).toBeTruthy();
    });
  });
});
