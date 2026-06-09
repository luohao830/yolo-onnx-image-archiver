import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "../../App";

describe("HomePage", () => {
  it("renders both entry mode links on home page", () => {
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

    const personFilterLink = screen.getByRole("link", { name: "人员筛选模式" });
    const advancedLink = screen.getByRole("link", { name: "高级模式" });

    expect(personFilterLink.getAttribute("href")).toBe("/person-filter");
    expect(advancedLink.getAttribute("href")).toBe("/advanced");
  });
});
