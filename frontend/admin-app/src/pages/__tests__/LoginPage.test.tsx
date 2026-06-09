import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { adminLogin } from "../../api/client";
import { LoginPage } from "../LoginPage";

vi.mock("../../api/client", () => ({
  adminLogin: vi.fn()
}));

describe("LoginPage", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("stores admin token after successful login", async () => {
    vi.mocked(adminLogin).mockResolvedValue({
      token: "admin-token-123"
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("管理员密钥"), {
      target: { value: "dev-secret" }
    });
    fireEvent.click(screen.getByRole("button", { name: "进入后台" }));

    await waitFor(() => {
      expect(adminLogin).toHaveBeenCalledWith("dev-secret");
      expect(localStorage.getItem("admin-token")).toBe("admin-token-123");
      expect(screen.getByText("模型管理")).toBeTruthy();
    });
  });

  it("shows backend error message when login fails", async () => {
    vi.mocked(adminLogin).mockRejectedValue(new Error("invalid secret"));

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("管理员密钥"), {
      target: { value: "bad-secret" }
    });
    fireEvent.click(screen.getByRole("button", { name: "进入后台" }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toBe("invalid secret");
    });
  });
});
