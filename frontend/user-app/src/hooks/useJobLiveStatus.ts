import { useCallback, useEffect, useRef, useState } from "react";

interface UseJobLiveStatusOptions<TSnapshot> {
  enabled: boolean;
  fetchSnapshot: () => Promise<TSnapshot>;
  subscribe?: (
    onEvent: () => void,
    onError: (error: Event | Error) => void,
  ) => () => void;
  isTerminal: (snapshot: TSnapshot) => boolean;
  pollIntervalMs?: number;
}

interface UseJobLiveStatusResult<TSnapshot> {
  snapshot: TSnapshot | null;
  errorMessage: string | null;
  realtimeFailed: boolean;
  refresh: () => Promise<void>;
}

const DEFAULT_POLL_INTERVAL_MS = 3000;

export function useJobLiveStatus<TSnapshot>({
  enabled,
  fetchSnapshot,
  subscribe,
  isTerminal,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
}: UseJobLiveStatusOptions<TSnapshot>): UseJobLiveStatusResult<TSnapshot> {
  const [snapshot, setSnapshot] = useState<TSnapshot | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [realtimeFailed, setRealtimeFailed] = useState(false);
  const [pollTick, setPollTick] = useState(0);
  const generationRef = useRef(0);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    const generation = generationRef.current;
    try {
      const next = await fetchSnapshot();
      if (generation !== generationRef.current) return;
      setSnapshot(next);
      setErrorMessage(null);
    } catch (error) {
      if (generation !== generationRef.current) return;
      setErrorMessage(error instanceof Error ? error.message : "获取任务状态失败");
    } finally {
      if (generation === generationRef.current) setPollTick((tick) => tick + 1);
    }
  }, [enabled, fetchSnapshot]);

  useEffect(() => {
    generationRef.current += 1;
    if (!enabled) {
      setSnapshot(null);
      setErrorMessage(null);
      setRealtimeFailed(false);
      return;
    }

    setSnapshot(null);
    setErrorMessage(null);
    setRealtimeFailed(false);
    void refresh();

    let unsubscribe: (() => void) | null = null;
    try {
      unsubscribe = subscribe?.(
        () => {
          void refresh();
        },
        () => {
          setRealtimeFailed(true);
        },
      ) ?? null;
    } catch {
      setRealtimeFailed(true);
    }

    return () => {
      generationRef.current += 1;
      try {
        unsubscribe?.();
      } catch {
        // ignore cleanup errors
      }
    };
  }, [enabled, refresh, subscribe]);

  useEffect(() => {
    if (!enabled) return;
    if (snapshot && isTerminal(snapshot)) return;

    const timer = setTimeout(() => {
      void refresh();
    }, pollIntervalMs);

    return () => clearTimeout(timer);
  }, [enabled, snapshot, isTerminal, pollIntervalMs, pollTick, refresh]);

  return {
    snapshot,
    errorMessage,
    realtimeFailed,
    refresh,
  };
}
