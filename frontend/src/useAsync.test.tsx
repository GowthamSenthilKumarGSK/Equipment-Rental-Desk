import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { useAsync } from "./useAsync";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useAsync", () => {
  it("is loading first, then has the data", async () => {
    const { result } = renderHook(() => useAsync("k", async () => "hello"));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeUndefined();
    await waitFor(() => expect(result.current.data).toBe("hello"));
    expect(result.current.loading).toBe(false);
  });

  it("turns a failure into an ApiError instead of throwing", async () => {
    const { result } = renderHook(() =>
      useAsync("k", async () => {
        throw new ApiError(404, "not_found", "Item 1 not found");
      }),
    );

    await waitFor(() => expect(result.current.error?.code).toBe("not_found"));
    expect(result.current.data).toBeUndefined();
  });

  it("ignores an answer that arrives after the key has changed", async () => {
    const slow = deferred<string>();
    const fast = deferred<string>();
    const { result, rerender } = renderHook(
      ({ key }) => useAsync(key, () => (key === "a" ? slow.promise : fast.promise)),
      { initialProps: { key: "a" } },
    );

    rerender({ key: "b" });
    await act(async () => fast.resolve("answer for b"));
    await act(async () => slow.resolve("late answer for a"));

    await waitFor(() => expect(result.current.data).toBe("answer for b"));
  });

  it("does not show the old key's data while the new key loads", async () => {
    const second = deferred<string>();
    const { result, rerender } = renderHook(
      ({ key }) => useAsync(key, async () => (key === "a" ? "first" : second.promise)),
      { initialProps: { key: "a" } },
    );
    await waitFor(() => expect(result.current.data).toBe("first"));

    rerender({ key: "b" });

    expect(result.current.data).toBeUndefined();
    expect(result.current.loading).toBe(true);
    await act(async () => second.resolve("second"));
    await waitFor(() => expect(result.current.data).toBe("second"));
  });

  it("keeps the data on screen while it reloads the same thing", async () => {
    let calls = 0;
    const { result } = renderHook(() => useAsync("k", async () => `call ${++calls}`));
    await waitFor(() => expect(result.current.data).toBe("call 1"));

    act(() => result.current.reload());

    expect(result.current.data).toBe("call 1"); // not blanked
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.data).toBe("call 2"));
  });
});
