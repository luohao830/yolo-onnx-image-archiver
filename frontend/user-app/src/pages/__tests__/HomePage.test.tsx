import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "../../App";

describe("HomePage", () => {
  it("renders both entry modes on home page", () => {
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

    expect(screen.getByText("人员筛选模式")).toBeDefined();
    expect(screen.getByText("高级模式")).toBeDefined();
  });
});
