import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";

vi.mock("../pages/ModelsPage", () => ({
  ModelsPage: () => <h1>模型管理页面</h1>
}));

vi.mock("../pages/ConfigsPage", () => ({
  ConfigsPage: () => <h1>系统配置页面</h1>
}));

vi.mock("../pages/JobsPage", () => ({
  JobsPage: () => <h1>任务监控页面</h1>
}));

vi.mock("../pages/UploadedArchivesPage", () => ({
  UploadedArchivesPage: () => <h1>压缩包管理页面</h1>
}));

vi.mock("../api/client", () => ({
  adminLogin: vi.fn()
}));

describe("App", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("logs out by clearing the stored admin token and showing login", () => {
    localStorage.setItem("admin-token", "token-123");

    render(
      <MemoryRouter initialEntries={["/models"]}>
        <App />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "登出" }));

    expect(localStorage.getItem("admin-token")).toBeNull();
    expect(localStorage.getItem("admin-auto-login-disabled")).toBe("1");
    expect(screen.getByLabelText("管理员密钥")).toBeTruthy();
  });
});
