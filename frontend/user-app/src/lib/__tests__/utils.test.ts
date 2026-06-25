import { describe, expect, it } from "vitest";

import { clampProgress, cn, formatSeconds, getFallbackProgress, isTerminalStatus } from "../utils";

describe("cn", () => {
  it("merges Tailwind classes", () => {
    expect(cn("px-2", "py-1")).toBe("px-2 py-1");
  });

  it("resolves conflicts with twMerge", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});

describe("formatSeconds", () => {
  it("returns em-dash for undefined or null", () => {
    expect(formatSeconds(undefined)).toBe("—");
    expect(formatSeconds(null)).toBe("—");
  });

  it("formats sub-second values as ms", () => {
    expect(formatSeconds(0.5)).toBe("500 ms");
    expect(formatSeconds(0.001)).toBe("1 ms");
  });

  it("formats second values with two decimals", () => {
    expect(formatSeconds(1)).toBe("1.00 s");
    expect(formatSeconds(3.5)).toBe("3.50 s");
  });
});

describe("isTerminalStatus", () => {
  it.each(["completed", "failed", "canceled"] as const)("returns true for %s", (status) => {
    expect(isTerminalStatus(status)).toBe(true);
  });

  it.each(["created", "uploaded", "running"] as const)("returns false for %s", (status) => {
    expect(isTerminalStatus(status)).toBe(false);
  });
});

describe("clampProgress", () => {
  it("clamps below 0 to 0", () => {
    expect(clampProgress(-5)).toBe(0);
  });

  it("clamps above 100 to 100", () => {
    expect(clampProgress(150)).toBe(100);
  });

  it("rounds to integer", () => {
    expect(clampProgress(45.7)).toBe(46);
  });

  it("passes valid values through", () => {
    expect(clampProgress(50)).toBe(50);
  });
});

describe("getFallbackProgress", () => {
  it("returns 0 for created and canceled", () => {
    expect(getFallbackProgress("created")).toBe(0);
    expect(getFallbackProgress("canceled")).toBe(0);
  });

  it("returns 100 for uploaded, completed, and failed", () => {
    expect(getFallbackProgress("uploaded")).toBe(100);
    expect(getFallbackProgress("completed")).toBe(100);
    expect(getFallbackProgress("failed")).toBe(100);
  });

  it("returns 0 for running (progress comes from events)", () => {
    expect(getFallbackProgress("running")).toBe(0);
  });
});
