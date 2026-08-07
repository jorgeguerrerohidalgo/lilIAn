"use client";

/**
 * usePoll — declarative polling hook for the matters page.
 *
 * The legacy implementation created `setInterval` inside event handlers
 * and tracked the handle in a local variable, which leaked intervals
 * when the component unmounted before completion (S3-08). This hook:
 *
 *   - Always clears the interval on unmount, even if no caller does.
 *   - Accepts a typed `done` predicate so callers can stop on any
 *     condition without managing the handle.
 *   - Returns ``stop()`` for callers that want to cancel early.
 *
 * Typical usage:
 *
 *   const stop = usePoll({
 *     intervalMs: 5000,
 *     maxAttempts: 60,
 *     task: async () => {
 *       const data = await fetchStatus();
 *       return { done: data.status === "processed", value: data };
 *     },
 *     onResult: (result) => result.done && doSomething(result.value),
 *   });
 */

import { useEffect, useRef } from "react";

export type PollTaskResult<T> = { done: boolean; value?: T };
export type PollTask<T> = () => Promise<PollTaskResult<T>>;

export interface UsePollOptions<T> {
  /** Milliseconds between ticks. */
  intervalMs: number;
  /** Maximum ticks before stopping. */
  maxAttempts: number;
  /** Async function returning `{ done, value }`. */
  task: PollTask<T>;
  /** Called after every successful task, including the final one. */
  onResult?: (result: PollTaskResult<T>) => void;
  /** Called once when the poll reaches `maxAttempts` without `done`. */
  onTimeout?: () => void;
  /** When false, the hook is a no-op. Useful to gate behind flags. */
  enabled?: boolean;
}

export function usePoll<T>(options: UsePollOptions<T>): () => void {
  const { intervalMs, maxAttempts, task, onResult, onTimeout, enabled = true } = options;
  const handleRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attemptsRef = useRef(0);
  const taskRef = useRef(task);
  const onResultRef = useRef(onResult);
  const onTimeoutRef = useRef(onTimeout);

  // Always read the latest callback without restarting the timer.
  taskRef.current = task;
  onResultRef.current = onResult;
  onTimeoutRef.current = onTimeout;

  useEffect(() => {
    if (!enabled) return undefined;

    handleRef.current = setInterval(async () => {
      attemptsRef.current += 1;
      let result: PollTaskResult<T>;
      try {
        result = await taskRef.current();
      } catch {
        // Swallow transient errors and let the next tick retry.
        if (attemptsRef.current >= maxAttempts) {
          if (handleRef.current !== null) {
            clearInterval(handleRef.current);
            handleRef.current = null;
          }
          onTimeoutRef.current?.();
        }
        return;
      }
      onResultRef.current?.(result);
      if (result.done || attemptsRef.current >= maxAttempts) {
        if (handleRef.current !== null) {
          clearInterval(handleRef.current);
          handleRef.current = null;
        }
        if (!result.done && attemptsRef.current >= maxAttempts) {
          onTimeoutRef.current?.();
        }
      }
    }, intervalMs);

    return () => {
      if (handleRef.current !== null) {
        clearInterval(handleRef.current);
        handleRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, maxAttempts, enabled]);

  return () => {
    if (handleRef.current !== null) {
      clearInterval(handleRef.current);
      handleRef.current = null;
    }
  };
}

/** Default poll configuration used by the matters detail page. */
export const MATTER_DOCUMENT_POLL = {
  intervalMs: 5_000,
  maxAttempts: 60, // 5 minutes
} as const;