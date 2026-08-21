"use client";

/**
 * ArticleReference — S4.3.
 *
 * Wraps a Chilean legal citation ("Art. 1545", "Art. 19 N°24",
 * "artículo 1545 del Código Civil") in a clickable chip that
 * jumps to the matching chunk in the document. When the source
 * chunk is not on the page, it falls back to a "no encontrado"
 * tooltip so the user isn't confused.
 *
 * Why a separate component rather than reusing CitationLink:
 * ``CitationLink`` is built around a structured Citation object
 * (quoted_text + source + relevance_score). The article mentions
 * in the analysis report are inline substrings of a longer
 * paragraph — we want to wrap them in place without rebuilding
 * the entire sentence as a citation tree.
 *
 * Visibility: the article name is rendered verbatim. The chip
 * just adds a hover affordance and a click handler.
 */

import { useState } from "react";

interface ArticleReferenceProps {
  /** The article number text to wrap, e.g. "Art. 1545". */
  article: string;
  /** Optional chunk id to jump to. If absent we show a "no ancla" tooltip. */
  chunkId?: string;
  /** Free-form description (e.g. "del Código Civil"). Shown next to the chip. */
  description?: string;
}

/**
 * Match an article reference in a longer text. We accept:
 *   - "Art. 1545"
 *   - "art. 1545 N°2"
 *   - "artículo 1545"
 *   - "Art. 19 N°24"
 *
 * The regex is conservative: it needs "Art." or "artículo" plus
 * a number, and optionally an inciso / N° suffix. We avoid
 * matching standalone numbers like "1545" because they almost
 * always appear in amounts.
 */
const ARTICLE_PATTERN =
  /(\bArt\.\s*\d+\b(?:\s*N[°º]\s*\d+)?|\bart[íi]culo\s*\d+\b)/gi;

export function ArticleReference({
  article,
  chunkId,
  description,
}: ArticleReferenceProps) {
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    if (!chunkId) {
      setFeedback("Sin anclaje al documento");
      window.setTimeout(() => setFeedback(null), 1800);
      return;
    }
    const target = document.querySelector(
      `[data-chunk-id="${chunkId}"]`,
    ) as HTMLElement | null;
    if (!target) {
      setFeedback("Fragmento no visible");
      window.setTimeout(() => setFeedback(null), 1800);
      return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.classList.add("ring-2", "ring-sky-400", "ring-offset-2");
    window.setTimeout(() => {
      target.classList.remove("ring-2", "ring-sky-400", "ring-offset-2");
    }, 1500);
  };

  const href = chunkId ? `#chunk-${chunkId}` : undefined;

  return (
    <span className="inline-flex items-center align-baseline">
      <a
        href={href}
        onClick={handleClick}
        className="inline-flex items-baseline gap-1 rounded bg-sky-50 px-1.5 py-0.5 text-sm font-semibold text-sky-800 underline decoration-dotted decoration-sky-400 hover:bg-sky-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
        title={chunkId ? "Ir al fragmento citado" : "Referencia legal (sin anclaje al documento)"}
      >
        {article}
        {description ? (
          <span className="font-normal text-sky-700"> {description}</span>
        ) : null}
      </a>
      {feedback ? (
        <span
          role="status"
          aria-live="polite"
          className="ml-2 text-xs text-amber-700"
        >
          {feedback}
        </span>
      ) : null}
    </span>
  );
}

/**
 * Render a block of text with article references auto-wrapped.
 * Use this in the analysis report (or any long-form LLM output)
 * to make every Chilean legal citation clickable without
 * re-prompting the model.
 *
 * Use `chunkResolver` when you have a deterministic mapping from
 * "Art. 1545" to a chunk id. When the resolver returns ``null``
 * the substring is rendered as a plain ArticleReference chip
 * (still clickable, but shows the "Sin anclaje" tooltip).
 */
export function ArticleReferenceText({
  text,
  chunkResolver,
}: {
  text: string;
  chunkResolver?: (article: string) => string | undefined;
}) {
  if (!text) return null;
  const parts: Array<string | { article: string; chunkId: string | undefined }> = [];
  let lastIndex = 0;
  // Reset the regex state because it's global.
  ARTICLE_PATTERN.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = ARTICLE_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push({
      article: match[0],
      chunkId: chunkResolver?.(match[0]),
    });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return (
    <>
      {parts.map((part, i) =>
        typeof part === "string" ? (
          <span key={i}>{part}</span>
        ) : (
          <ArticleReference
            key={i}
            article={part.article}
            chunkId={part.chunkId}
          />
        ),
      )}
    </>
  );
}
