import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "../../App";

describe("HomePage", () => {
  it("renders the single upload workspace and admin entry", () => {
    render(
      <MemoryRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true
        }}
        initialEntries={["/"]}
      >
        <App />
      </MemoryRouter>,
    );

    const adminLink = screen.getByRole("link", { name: "管理员配置" });

    expect(screen.getByRole("heading", { name: "上传图片后直接查看处理进度" })).toBeTruthy();
    expect(screen.getByLabelText("上传图片或压缩包")).toBeTruthy();
    expect(screen.getByRole("button", { name: "开始处理" })).toHaveProperty("disabled", true);
    expect(adminLink.getAttribute("href")).toBe("/admin/configs");
    expect(screen.queryByText("任务凭证查询")).toBeNull();
  });
});
