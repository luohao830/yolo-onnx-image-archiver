import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useJobLiveStatus } from "../useJobLiveStatus";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const TERMINAL_SNAPSHOT = { status: "completed" as const, progress: 100 };
const ACTIVE_SNAPSHOT = { status: "running" as const, progress: 50 };

describe("useJobLiveStatus", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.resetAllMocks();
  });

  it("returns initial null snapshot and fetches on enable", async () => {
    const fetch = vi.fn().mockResolvedValue(ACTIVE_SNAPSHOT);

    const { result } = renderHook(() =>
      useJobLiveStatus({
        enabled: true,
        fetchSnapshot: fetch,
        isTerminal: () => false,
      }),
    );

    // 初始状态
    expect(result.current.snapshot).toBeNull();
    expect(result.current.errorMessage).toBeNull();

    // 首次拉取
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(result.current.snapshot).toEqual(ACTIVE_SNAPSHOT);
  });

  it("does not fetch when disabled", async () => {
    const fetch = vi.fn().mockResolvedValue(ACTIVE_SNAPSHOT);

    renderHook(() =>
      useJobLiveStatus({
        enabled: false,
        fetchSnapshot: fetch,
        isTerminal: () => false,
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetch).not.toHaveBeenCalled();
  });

  it("polls until terminal state", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(ACTIVE_SNAPSHOT)
      .mockResolvedValueOnce(ACTIVE_SNAPSHOT)
      .mockResolvedValueOnce(TERMINAL_SNAPSHOT);

    let terminalCalls = 0;
    const isTerminal = vi.fn(() => {
      terminalCalls += 1;
      return terminalCalls >= 3;
    });

    const { result } = renderHook(() =>
      useJobLiveStatus({
        enabled: true,
        fetchSnapshot: fetch,
        isTerminal,
        pollIntervalMs: 2000,
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetch).toHaveBeenCalledTimes(1);

    // 轮询第 1 次
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(fetch).toHaveBeenCalledTimes(2);

    // 轮询第 2 次 — 进入终态
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(fetch).toHaveBeenCalledTimes(3);

    // 终态后停止轮询
    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000);
    });
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(result.current.snapshot).toEqual(TERMINAL_SNAPSHOT);
  });

  it("sets errorMessage on fetch failure and recovers", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("network error"))
      .mockResolvedValueOnce(ACTIVE_SNAPSHOT);

    const { result } = renderHook(() =>
      useJobLiveStatus({
        enabled: true,
        fetchSnapshot: fetch,
        isTerminal: () => false,
        pollIntervalMs: 2000,
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.errorMessage).toBe("network error");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(result.current.errorMessage).toBeNull();
    expect(result.current.snapshot).toEqual(ACTIVE_SNAPSHOT);
  });

  it("sets realtimeFailed when SSE subscribe errors", async () => {
    const fetch = vi.fn().mockResolvedValue(ACTIVE_SNAPSHOT);
    const subscribe = vi.fn(() => {
      throw new Error("SSE not available");
    });

    const { result } = renderHook(() =>
      useJobLiveStatus({
        enabled: true,
        fetchSnapshot: fetch,
        subscribe,
        isTerminal: () => false,
        pollIntervalMs: 2000,
      }),
    );

    // subscribe 同步抛出 → realtimeFailed 立即为 true
    expect(result.current.realtimeFailed).toBe(true);

    // 拉取仍通过初始 effect 触发
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("stops polling on cleanup", async () => {
    const fetch = vi.fn().mockResolvedValue(ACTIVE_SNAPSHOT);

    const { unmount } = renderHook(() =>
      useJobLiveStatus({
        enabled: true,
        fetchSnapshot: fetch,
        isTerminal: () => false,
        pollIntervalMs: 2000,
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetch).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("discards stale fetch results when re-enabled", async () => {
    const first = deferred<{ status: "running"; progress: number }>();
    const second = vi.fn().mockResolvedValue(ACTIVE_SNAPSHOT);
    const fetch = vi.fn().mockReturnValueOnce(first.promise).mockImplementationOnce(second);

    const { rerender, result } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useJobLiveStatus({
          enabled,
          fetchSnapshot: fetch,
          isTerminal: () => false,
          pollIntervalMs: 2000,
        }),
      { initialProps: { enabled: true } },
    );

    // 先 disabled 再 enabled，上一代 fetch 的结果应被丢弃。
    rerender({ enabled: false });
    rerender({ enabled: true });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // 完成第一个（过期）的 promise。
    await act(async () => {
      first.resolve({ status: "running", progress: 10 });
    });

    expect(result.current.snapshot).toEqual(ACTIVE_SNAPSHOT);
  });
});
