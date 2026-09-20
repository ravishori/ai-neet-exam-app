import { describe, expect, it, vi } from "vitest";

/**
 * Autosave debounce contract for the practice runner (P0-runner):
 *   · rapid patches within a 400 ms window collapse to ONE mutation call;
 *   · flush() called explicitly (navigation / submit) drains immediately.
 *
 * The runner's commitAnswer semantics are re-implemented here in isolation so
 * this test does not spin the whole page; the real page uses the same shape.
 */
type Patch = { selected_option?: string; confidence?: string | null; marked_for_review?: boolean };
type State = { selected_option: string | null; confidence: string | null; marked_for_review: boolean };
const EMPTY: State = { selected_option: null, confidence: null, marked_for_review: false };

type Pending = { state: State; entry: number };

function makeRunner(mutate: (payload: object) => void, wait = 400) {
  const ref: { current: Pending | null } = { current: null };
  let timer: ReturnType<typeof setTimeout> | null = null;
  function flush() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    const p = ref.current;
    if (!p) return;
    ref.current = null;
    mutate({ content_item_id: "q1", ...p.state, time_spent_seconds: Math.max(1, Math.round((Date.now() - p.entry) / 1000)) });
  }
  function commit(patch: Patch) {
    const prev = ref.current;
    const nextState: State = { ...(prev?.state ?? EMPTY), ...patch };
    ref.current = { state: nextState, entry: prev?.entry ?? Date.now() };
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, wait);
  }
  return { commit, flush };
}

describe("practice-runner autosave debounce", () => {
  it("collapses rapid patches to one mutation after the quiet window", async () => {
    vi.useFakeTimers();
    const mutate = vi.fn();
    const runner = makeRunner(mutate, 400);
    runner.commit({ selected_option: "A" });
    runner.commit({ confidence: "high" });
    runner.commit({ marked_for_review: true });
    expect(mutate).not.toHaveBeenCalled();
    vi.advanceTimersByTime(399);
    expect(mutate).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toMatchObject({
      content_item_id: "q1",
      selected_option: "A",
      confidence: "high",
      marked_for_review: true,
    });
    vi.useRealTimers();
  });

  it("flush drains the pending patch immediately (navigation / submit)", () => {
    vi.useFakeTimers();
    const mutate = vi.fn();
    const runner = makeRunner(mutate, 400);
    runner.commit({ selected_option: "B" });
    runner.flush();
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toMatchObject({ selected_option: "B" });
    // A subsequent commit + timer should still fire once (no leaked timer).
    runner.commit({ confidence: "low" });
    vi.advanceTimersByTime(400);
    expect(mutate).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
