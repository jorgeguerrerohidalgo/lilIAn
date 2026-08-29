"""HTML parser for Chilean-norm text — hierarchical chunking.

The BCN SPA returns an Angular shell when scraped via ``httpx``, so the
crawler falls back to local text dumps (`.txt`) for the bulk of Tier 1
and to the AKN XML manifest for Tier 2. Either way, the raw text is
laid out with indent-based hierarchy:

    LEY NÚM. 21.719
    ...
         "Artículo 1°.- Objeto y ámbito de aplicación. La presente ley tiene por objeto ...
         1) Incorpórase el siguiente artículo 1° bis:
              "Artículo 1° bis.- Ámbito de aplicación territorial. ...

For Códigos the layout is more structured:

    LIBRO PRIMERO
    TÍTULO I
    CAPÍTULO 1
    Artículo 1°.- ...

This module produces a flat list of ``ParsedChunk`` records where each
chunk carries the current ``libro / titulo / capitulo / articulo /
inciso / numeral / letra`` (whatever applies). Downstream code
(:mod:`scripts.hierarchical_chunker`) wraps these into ``LawChunk``
rows with ``jerarquia_path`` and ``parent_chunk_id`` wires.

The parser is deliberately tolerant: if it cannot detect a structural
boundary (eg. an exotic norm that lacks ``LIBRO`` headings) it falls
back to article-level chunking. Every parse is logged with the
unrecognised patterns so the operator can fix them.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("lilian.html_parser")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ParsedChunk:
    """One logical chunk of legal text with its hierarchical context.

    ``parent_hint`` is a human-readable breadcrumb (``"Libro I"``)
    that the chunker can persist in ``law_chunks.jerarquia_path``.
    The chunker wires ``parent_chunk_id`` separately after the DB
    round-trip because the parent may already exist from a previous
    ingest.
    """

    article_number: Optional[str] = None
    libro: Optional[str] = None
    titulo: Optional[str] = None
    capitulo: Optional[str] = None
    inciso: Optional[str] = None
    numeral: Optional[str] = None
    letra: Optional[str] = None
    content: str = ""
    chunk_index: int = 0
    parent_hint: str = ""  # human-readable breadcrumb for the chunker

    def hierarchy_path(self) -> str:
        """Slash-separated breadcrumb for ``law_chunks.jerarquia_path``."""
        parts = []
        for piece in (self.libro, self.titulo, self.capitulo, self.article_number):
            if piece:
                parts.append(piece)
        if self.inciso:
            parts.append(f"inciso {self.inciso}")
        if self.numeral:
            parts.append(f"numeral {self.numeral}")
        if self.letra:
            parts.append(f"letra {self.letra}")
        return "/" + "/".join(parts) if parts else ""


@dataclass
class ParseResult:
    chunks: list[ParsedChunk] = field(default_factory=list)
    detected_structure: str = "unknown"  # 'codigo' | 'ley' | 'unknown'
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

# LIBRO / TÍTULO / CAPÍTULO / SECCIÓN headings appear in CAPS in Códigos.
# We use [ \t]* (not \s*) to avoid eating the preceding \n — that would
# desync the offsets used to slice the text into per-block bodies.
_LIBRO_RE = re.compile(r"^[ \t]*LIBRO\s+([IVXLCDM]+|\S.*?)\s*$", re.IGNORECASE | re.MULTILINE)
_TITULO_RE = re.compile(r"^[ \t]*TÍTULO\s+([IVXLCDM]+|\S.*?)\s*$", re.IGNORECASE | re.MULTILINE)
_CAPITULO_RE = re.compile(r"^[ \t]*CAPÍTULO\s+([IVXLCDM]+|\d+|\S.*?)\s*$", re.IGNORECASE | re.MULTILINE)
_SECCION_RE = re.compile(r"^[ \t]*SECCIÓN\s+([IVXLCDM]+|\d+|\S.*?)\s*$", re.IGNORECASE | re.MULTILINE)
_PARRAFO_RE = re.compile(r"^[ \t]*PÁRRAFO\s+([IVXLCDM]+|\d+|\S.*?)\s*$", re.IGNORECASE | re.MULTILINE)

# Article marker — the universal pattern across Chilean norms.
# Captures the article number including bis/ter suffixes and the °/º
# typographic variants. Example matches:
#   "Artículo 1°.-"        → group "1" + suffix ""
#   "Artículo 1° bis.-"    → group "1" + suffix " bis"
#   "Artículo primero.-"   → group "primero"
#   "Artículo 23.-"        → group "23" + suffix ""
_ARTICLE_RE = re.compile(
    r"""
    [ \t]*\"?(?:Art\.\s*|Artículo\s+)
    (?P<num>\w+)                # the article identifier (digits or word)
    (?:\s*(?P<suf>bis|ter|tercero|cuarto|quinto))?   # optional suffix
    \s*[°º]?\s*[\.\-:]?          # optional °, separator
    \s*
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A literal child article that some norms introduce with a numbering
# offset like "Artículo 1° A" or "Artículo 1°-1".
_ARTICLE_ALT_RE = re.compile(
    r"""^\s*\"?(?:Art\.\s*|Artículo\s+)
        (?P<num>\d+)               # numeric only (vs. the universal _ARTICLE_RE)
        \s*[°º]?\s*(?P<suf>[A-Z\d]+)
        \s*[\.\-:]\s*
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

# Inciso / numeral / letra inside an article body.
_INCISO_RE = re.compile(r"^\s*Inciso\s+(?:final|primero|segundo|tercero|\d+)\s*[-—:]\s*", re.IGNORECASE | re.MULTILINE)
_NUMERAL_RE = re.compile(r"^\s*(\d+)\s*\)\s+", re.MULTILINE)
_LETRA_RE = re.compile(r"^\s*([a-z])\)\s+", re.IGNORECASE | re.MULTILINE)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class HierarchicalParser:
    """Stateful walker over a Chilean-norm plain-text dump.

    Usage::

        parser = HierarchicalParser()
        result = parser.parse(open("ley_21719.txt").read())
        for chunk in result.chunks:
            print(chunk.hierarchy_path(), chunk.content[:80])

    The parser detects three top-level structures:

    - **Codigo**: heavy use of LIBRO / TÍTULO / CAPÍTULO headings. We
      detect by scanning for any of these tokens in the first 200
      non-empty lines. If found, hierarchy is tracked at four levels.
    - **Ley**: occasional PÁRRAFO + flat Articulo-only. Two levels.
    - **Unknown**: article-only fallback.

    The parser is robust to whitespace, leading-quote characters and
    surrounding punctuation (``".-"``, ``":-"``, ``"-"``) — Chilean
    publishers are inconsistent.
    """

    def __init__(self, *, max_chunk_chars: int = 2200) -> None:
        # Sentinel: long articles get split at this many characters.
        # 2.200 leaves room for the embedding model (1536-dim) and
        # citation context. Long Codes (Codigo Civil has 2.596 articles)
        # may need smaller chunks; tune per corpus.
        self.max_chunk_chars = max_chunk_chars

    def parse(self, text: str) -> ParseResult:
        result = ParseResult()
        text = self._strip_html(text) if "<" in text else text
        text = self._normalise(text)

        result.detected_structure = self._detect_structure(text)
        if result.detected_structure == "codigo":
            chunks = self._parse_with_libros(text, result)
        else:
            chunks = self._parse_articles_only(text, result)

        # Number chunks globally (1-based) so the DB row order matches.
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        result.chunks = chunks
        return result

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_html(text: str) -> str:
        """Minimal HTML→text — same approach as ingest_law_21719."""
        text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</\s*(p|div|li|h\d|tr|td|th)\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = (
            text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )
        return text

    @staticmethod
    def _normalise(text: str) -> str:
        """Collapse repeated whitespace inside lines; preserve paragraphs."""
        # Strip BOM.
        if text.startswith("﻿"):
            text = text[1:]
        # Normalise newlines.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse runs of spaces/tabs inside lines (but keep the \n).
        out_lines = []
        for line in text.split("\n"):
            line = re.sub(r"[ \t]+", " ", line).rstrip()
            out_lines.append(line)
        text = "\n".join(out_lines)
        # Collapse 3+ blank lines into one.
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ------------------------------------------------------------------
    # Structure detection
    # ------------------------------------------------------------------

    def _detect_structure(self, text: str) -> str:
        sample = "\n".join(text.split("\n")[:200])
        signals = sum(
            bool(re.search(p, sample, re.IGNORECASE))
            for p in (r"^LIBRO\s", r"^TÍTULO\s", r"^CAPÍTULO\s")
        )
        if signals >= 2:
            return "codigo"
        # Some Códigos only use PARRAFO. Treat those as flat-ley.
        if re.search(r"^PÁRRAFO\s", sample, re.IGNORECASE | re.MULTILINE):
            return "ley"
        return "ley" if _ARTICLE_RE.search(text) else "unknown"

    # ------------------------------------------------------------------
    # Top-level parsers
    # ------------------------------------------------------------------

    def _parse_articles_only(self, text: str, result: ParseResult) -> list[ParsedChunk]:
        """Article-only parse (laws, decrees, anything without LIBRO/TÍTULO)."""
        chunks: list[ParsedChunk] = []
        matches = list(_ARTICLE_RE.finditer(text))
        if not matches:
            # Give up: a single whole-doc chunk.
            chunk = ParsedChunk(
                article_number=None,
                content=text.strip(),
                parent_hint="(no-articles-detected)",
            )
            if chunk.content:
                chunks.append(chunk)
                result.warnings.append("no articles detected; single-chunk fallback")
            return chunks

        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            body = self._strip_inner_article_refs(body)
            if not body or len(body) < 5:
                continue

            article_num = m.group("num")
            suffix = m.group("suf") or ""

            chunks.extend(self._split_long_body(
                article_number=article_num + (f" {suffix}" if suffix else ""),
                libro=None,
                titulo=None,
                capitulo=None,
                body=body,
                result=result,
            ))

        if not chunks:
            result.warnings.append("articles detected but produced 0 chunks (all too short?)")
        return chunks

    def _parse_with_libros(self, text: str, result: ParseResult) -> list[ParsedChunk]:
        """Hierarchical parse for Códigos with LIBRO / TÍTULO / CAPÍTULO.

        Strategy:
        1. Tokenise the document into blocks separated by structural
           headings (LIBRO / TÍTULO / CAPÍTULO / SECCIÓN / PÁRRAFO).
        2. For each block, slice by ``_ARTICLE_RE`` and emit chunks
           with the inherited ``libro`` / ``titulo`` / ``capitulo``.
        """
        blocks = self._split_into_blocks(text)
        chunks: list[ParsedChunk] = []
        current_libro = None
        current_titulo = None
        current_capitulo = None
        current_seccion = None

        for kind, marker, body in blocks:
            if kind == "libro":
                current_libro = marker
                current_titulo = None
                current_capitulo = None
                current_seccion = None
                continue
            if kind == "titulo":
                current_titulo = marker
                current_capitulo = None
                current_seccion = None
                continue
            if kind == "capitulo":
                current_capitulo = marker
                current_seccion = None
                continue
            if kind == "seccion":
                current_seccion = marker
                continue
            if kind == "parrafo":
                # PÁRRAFO is optional; we keep it in parent_hint.
                pass

            # Slice articles inside this block.
            article_matches = list(_ARTICLE_RE.finditer(body))
            if not article_matches:
                # No articles — promote the whole block to a single
                # chunk tagged with the surrounding heading context.
                if body.strip():
                    chunks.append(self._build_chunk(
                        article_number=None,
                        libro=current_libro,
                        titulo=current_titulo,
                        capitulo=current_capitulo,
                        body=body.strip(),
                        parent_hint=" ".join(filter(None, [
                            current_libro, current_titulo, current_capitulo,
                            current_seccion, marker if kind == "parrafo" else None,
                        ])),
                    ))
                continue

            for i, m in enumerate(article_matches):
                start = m.end()
                end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(body)
                article_body = body[start:end].strip()
                article_body = self._strip_inner_article_refs(article_body)
                if not article_body or len(article_body) < 5:
                    continue
                article_num = m.group("num")
                suffix = m.group("suf") or ""
                chunks.extend(self._split_long_body(
                    article_number=article_num + (f" {suffix}" if suffix else ""),
                    libro=current_libro,
                    titulo=current_titulo,
                    capitulo=current_capitulo,
                    body=article_body,
                    result=result,
                ))

        if not chunks:
            result.warnings.append("codigo parse produced 0 chunks; falling back to article-only")
            return self._parse_articles_only(text, result)
        return chunks

    def _split_into_blocks(self, text: str) -> list[tuple[str, Optional[str], str]]:
        """Return ``[(kind, marker, body), ...]`` blocks.

        ``kind`` is one of ``libro``, ``titulo``, ``capitulo``, ``seccion``,
        ``parrafo``, ``body``. ``marker`` is the heading text after
        the keyword (eg. ``"PRIMERO"``); ``None`` for plain bodies.
        """
        # Find every structural heading offset.
        markers: list[tuple[int, str, str]] = []
        for regex, kind in (
            (_LIBRO_RE, "libro"),
            (_TITULO_RE, "titulo"),
            (_CAPITULO_RE, "capitulo"),
            (_SECCION_RE, "seccion"),
            (_PARRAFO_RE, "parrafo"),
        ):
            for m in regex.finditer(text):
                markers.append((m.start(), kind, m.group(1).strip()))
        markers.sort(key=lambda t: t[0])

        if not markers:
            return [("body", None, text)]

        blocks: list[tuple[str, Optional[str], str]] = []
        # Walk the markers; each block spans from this marker to the
        # next. If the first marker isn't at position 0, prepend a
        # preamble block with kind='body'.
        if markers[0][0] > 0:
            blocks.append(("body", None, text[: markers[0][0]]))
        for i, (offset, kind, marker) in enumerate(markers):
            next_offset = markers[i + 1][0] if i + 1 < len(markers) else len(text)
            body = text[offset:next_offset]
            # Strip the heading line itself from the body — keep only
            # the content that follows it within the same block.
            line_end = text.find("\n", offset)
            if line_end == -1 or line_end >= next_offset:
                # The heading is the whole block.
                blocks.append((kind, marker, ""))
                continue
            body_content = text[line_end + 1:next_offset].strip()
            blocks.append((kind, marker, body_content))
        return blocks

    # ------------------------------------------------------------------
    # Chunk assembly
    # ------------------------------------------------------------------

    def _build_chunk(
        self,
        *,
        article_number: Optional[str],
        libro: Optional[str],
        titulo: Optional[str],
        capitulo: Optional[str],
        body: str,
        parent_hint: str,
    ) -> ParsedChunk:
        chunk = ParsedChunk(
            article_number=article_number,
            libro=libro,
            titulo=titulo,
            capitulo=capitulo,
            content=body,
            parent_hint=parent_hint,
        )
        return chunk

    def _split_long_body(
        self,
        *,
        article_number: Optional[str],
        libro: Optional[str],
        titulo: Optional[str],
        capitulo: Optional[str],
        body: str,
        result: ParseResult,
    ) -> list[ParsedChunk]:
        """If ``body`` is longer than ``max_chunk_chars``, split at inciso
        or numeric boundaries when possible; otherwise naive window."""
        if len(body) <= self.max_chunk_chars:
            return [self._build_chunk(
                article_number=article_number,
                libro=libro,
                titulo=titulo,
                capitulo=capitulo,
                body=body,
                parent_hint=" ".join(filter(None, [libro, titulo, capitulo, article_number])),
            )]

        # First try to split at inciso boundaries.
        inciso_matches = list(_INCISO_RE.finditer(body))
        if len(inciso_matches) >= 2:
            chunks = []
            for i, m in enumerate(inciso_matches):
                start = m.start()
                end = inciso_matches[i + 1].start() if i + 1 < len(inciso_matches) else len(body)
                sub = body[start:end].strip()
                if sub:
                    chunks.append(self._build_chunk(
                        article_number=article_number,
                        libro=libro,
                        titulo=titulo,
                        capitulo=capitulo,
                        body=sub,
                        parent_hint=" ".join(filter(None, [libro, titulo, capitulo, article_number])),
                    ))
            return chunks

        # Naive window at max_chunk_chars, preserving word boundaries.
        chunks = []
        for k in range(0, len(body), self.max_chunk_chars):
            sub = body[k:k + self.max_chunk_chars].rsplit(" ", 1)[0]
            if sub:
                chunks.append(self._build_chunk(
                    article_number=article_number,
                    libro=libro,
                    titulo=titulo,
                    capitulo=capitulo,
                    body=sub,
                    parent_hint=" ".join(filter(None, [libro, titulo, capitulo, article_number])),
                ))
        result.warnings.append(
            f"article {article_number} exceeded max_chunk_chars ({len(body)} chars); split naively"
        )
        return chunks

    @staticmethod
    def _strip_inner_article_refs(text: str) -> str:
        """Drop the 'Artículo N°' marker that the body of an article
        starts with — the article number is already on the chunk."""
        m = _ARTICLE_RE.match(text)
        if m:
            return text[m.end():].lstrip()
        return text


# Lookup used by ``_split_into_blocks`` if we ever want to strip the
# heading line by keyword length (currently we use find('\n')).
_HEADER_KINDS: dict[str, int] = {
    "libro": 5,
    "titulo": 7,
    "capitulo": 9,
    "seccion": 8,
    "parrafo": 7,
}
