"use client";

/**
 * Tooltip — S6.2.
 *
 * Pure CSS + a tiny hover/focus delay state. Zero external deps, no
 * Radix/Floating UI. The component wraps the trigger element so existing
 * markup stays intact — callers just wrap their button / link / input
 * inside `<Tooltip label="…">`.
 *
 * Why 200ms delay: matches the convention set by Material / GitHub /
 * Linear tooltips. A short delay avoids tooltip flashes when the cursor
 * crosses an element on the way to a real target.
 *
 * Positioning: tooltip renders absolutely below the trigger by default.
 * For wide forms / sidebar items where there isn't enough room below,
 * pass ``side="right"`` (or ``"left"`` / ``"top"``).
 *
 * All copy is Spanish — see the tooltip map in
 * ``apps/frontend/lib/tooltips.ts`` for the canonical strings.
 */

import {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

export type TooltipSide = "top" | "right" | "bottom" | "left";

export interface TooltipProps {
  /** Tooltip copy in Spanish. Plain text or a short node. */
  label: ReactNode;
  /** Optional accessible label override (defaults to ``label``). */
  ariaLabel?: string;
  /** Which side of the trigger the tooltip anchors to. */
  side?: TooltipSide;
  /** Delay in ms before showing on hover. Defaults to 200ms. */
  delayMs?: number;
  /** Disable the tooltip entirely (rendering still happens). */
  disabled?: boolean;
  /** The trigger element. Should be focusable for keyboard access. */
  children: ReactElement;
}

const SIDE_OFFSET = 8;

const sideStyles: Record<TooltipSide, string> = {
  top: `bottom-full left-1/2 -translate-x-1/2 mb-[${SIDE_OFFSET}px]`,
  right: `left-full top-1/2 -translate-y-1/2 ml-[${SIDE_OFFSET}px]`,
  bottom: `top-full left-1/2 -translate-x-1/2 mt-[${SIDE_OFFSET}px]`,
  left: `right-full top-1/2 -translate-y-1/2 mr-[${SIDE_OFFSET}px]`,
};

const arrowStyles: Record<TooltipSide, string> = {
  top: "top-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-b-transparent border-t-slate-900",
  right: "right-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-r-transparent border-l-slate-900",
  bottom: "bottom-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-t-transparent border-b-slate-900",
  left: "left-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-l-transparent border-r-slate-900",
};

export function Tooltip({
  label,
  ariaLabel,
  side = "top",
  delayMs = 200,
  disabled = false,
  children,
}: TooltipProps) {
  const [open, setOpen] = useState(false);
  const [hoverTimer, setHoverTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const id = useId();

  const cancelTimer = useCallback(() => {
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
      setHoverTimer(null);
    }
  }, [hoverTimer]);

  const show = useCallback(() => {
    cancelTimer();
    const t = setTimeout(() => setOpen(true), delayMs);
    setHoverTimer(t);
  }, [cancelTimer, delayMs]);

  const hide = useCallback(() => {
    cancelTimer();
    setOpen(false);
  }, [cancelTimer]);

  // Hide on Escape — small a11y nicety.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => () => cancelTimer(), [cancelTimer]);

  // Clone the trigger so we can attach our own hover/focus listeners.
  // We keep all original props (className, aria-*, onClick, …) intact.
  const trigger = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        onMouseEnter: (e: unknown) => {
          show();
          const child = children as ReactElement<{
            onMouseEnter?: (...args: unknown[]) => unknown;
          }>;
          child.props.onMouseEnter?.(e);
        },
        onMouseLeave: (e: unknown) => {
          hide();
          const child = children as ReactElement<{
            onMouseLeave?: (...args: unknown[]) => unknown;
          }>;
          child.props.onMouseLeave?.(e);
        },
        onFocus: (e: unknown) => {
          show();
          const child = children as ReactElement<{
            onFocus?: (...args: unknown[]) => unknown;
          }>;
          child.props.onFocus?.(e);
        },
        onBlur: (e: unknown) => {
          hide();
          const child = children as ReactElement<{
            onBlur?: (...args: unknown[]) => unknown;
          }>;
          child.props.onBlur?.(e);
        },
        "aria-describedby": open ? id : undefined,
      })
    : children;

  if (disabled) {
    return <>{trigger}</>;
  }

  return (
    <span ref={wrapperRef} className="relative inline-flex">
      {trigger}
      {open && (
        <span
          id={id}
          role="tooltip"
          aria-label={typeof ariaLabel === "string" ? ariaLabel : undefined}
          className={`pointer-events-none absolute z-50 max-w-xs whitespace-normal rounded-md bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg ${sideStyles[side]}`}
        >
          {label}
          <span
            aria-hidden="true"
            className={`absolute h-0 w-0 border-4 ${arrowStyles[side]}`}
          />
        </span>
      )}
    </span>
  );
}
