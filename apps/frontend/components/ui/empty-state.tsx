/**
 * EmptyState — S1.4.
 *
 * Reusable empty-state block for any list (matters, documents, alerts,
 * precedents, clients). The contract:
 *
 *   - A meaningful Spanish title (1 line, < 8 words).
 *   - One short description (≤ 140 chars) that explains when this state
 *     occurs, not why it's empty in the abstract.
 *   - **Exactly one primary CTA** (per the Sprint 1 brief). Multiple
 *     secondary actions belong in a single wrapper, NOT multiple buttons.
 *   - An optional decorative icon (rendered above the title).
 *   - Accessible: the title uses role="status" with aria-live="polite"
 *     so screen readers announce the empty state on first paint.
 */

import type { ReactNode } from "react";

interface EmptyStateProps {
  /** Spanish title (≤ 8 words). */
  title: string;
  /** Spanish body text. Keep ≤ 140 chars. */
  description: string;
  /** One primary CTA — the entire tree (typically a Button or Link). */
  action: ReactNode;
  /** Optional secondary action rendered below the primary one. */
  secondary?: ReactNode;
  /** Optional icon node — typically an inline SVG. Decorative. */
  icon?: ReactNode;
  /** Optional tone: "neutral" (default) or "warm" for stronger emphasis. */
  tone?: "neutral" | "warm";
  /** Optional container data attribute so other features (e.g. tours)
   *  can anchor their highlights on this element. */
  "data-tour-target"?: string;
}

export function EmptyState({
  title,
  description,
  action,
  secondary,
  icon,
  tone = "neutral",
  ...rest
}: EmptyStateProps) {
  // Tone is intentionally a constant — the visual palette is mapped here
  // and stays consistent across all callers. Adding new tones requires
  // updating both this component and the design tokens file.
  const accent = tone === "warm"
    ? "bg-coral/10 text-coral"
    : "bg-soft text-ink/40";

  return (
    <div
      className="flex flex-col items-center justify-center text-center px-6 py-16 max-w-lg mx-auto"
      role="status"
      aria-live="polite"
      data-tour-target={rest["data-tour-target"]}
    >
      {icon && (
        <div
          aria-hidden="true"
          className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-5 ${accent}`}
        >
          {icon}
        </div>
      )}
      <h2 className="text-lg font-heading font-semibold text-ink mb-2">
        {title}
      </h2>
      <p className="text-ink/60 mb-6 max-w-sm">{description}</p>
      <div className="w-full max-w-xs space-y-3 flex flex-col">
        {action}
        {secondary}
      </div>
    </div>
  );
}
