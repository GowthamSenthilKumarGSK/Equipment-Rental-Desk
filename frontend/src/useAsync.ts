import { useEffect, useRef, useState } from "react";
import { toApiError, type ApiError } from "./api";

interface Settled<T> {
  runKey: string; // identifies one request: the caller's key plus how many times it was reloaded
  key: string;
  data?: T;
  error?: ApiError;
}

export interface AsyncState<T> {
  /** The latest data for `key`. Kept while a reload is running, so the page does not flash empty. */
  data: T | undefined;
  error: ApiError | undefined;
  loading: boolean;
  reload: () => void;
}

/**
 * Loads data from the API. `key` must change whenever the request would (for example the item id
 * and filters joined into a string): a changed key discards the old data and starts a new request,
 * and a response that arrives after the key changed again is ignored.
 */
export function useAsync<T>(key: string, load: (signal: AbortSignal) => Promise<T>): AsyncState<T> {
  const [reloads, setReloads] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>();
  const latestLoad = useRef(load);
  useEffect(() => {
    latestLoad.current = load;
  });

  const runKey = `${key}#${reloads}`;
  useEffect(() => {
    const controller = new AbortController();
    latestLoad.current(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setSettled({ runKey, key, data });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setSettled({ runKey, key, error: toApiError(error) });
      },
    );
    return () => controller.abort();
  }, [key, runKey]);

  const current = settled?.runKey === runKey ? settled : undefined;
  return {
    data: settled?.key === key ? settled.data : undefined,
    error: current?.error,
    loading: current === undefined,
    reload: () => setReloads((count) => count + 1),
  };
}
