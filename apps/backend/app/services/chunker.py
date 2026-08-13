import re

from app.models.legal_area import LegalArea

_PDF_PAGE_BOUNDARY = re.compile(r"--- PDF.*?---", re.IGNORECASE)
_PAGE_WINDOW = 500  # max chars of page text used to compute page_number chunk-side
_DEFAULT_CHUNK_SIZE = 1000
_DEFAULT_OVERLAP = 200
_DEFAULT_MIN_CHUNK_SIZE = 200


def split_text_into_chunks(
    text: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_OVERLAP,
    min_chunk_size: int = _DEFAULT_MIN_CHUNK_SIZE,
) -> list[dict]:
    """Greedy chunker that respects sentence boundaries when feasible.

    S4-15: refactored from a 75-line function with three inline concerns
    (boundary-finding, page-map, chunk-building) into a 4-step pipeline:
    normalize → build page map → emit chunks → renumber.

    Behavior is unchanged: chunks are emitted with content, chunk_index,
    page_number, and section_title.
    """
    short = _normalize_short_text(text, min_chunk_size)
    if short is not None:
        return short

    text = _normalize_text(text)
    page_map = _build_page_map(text)

    return _emit_chunks(text, page_map, chunk_size, overlap, min_chunk_size)


def _normalize_short_text(text: str, min_chunk_size: int) -> list[dict] | None:
    """Return a single chunk if text is below the minimum size threshold.

    Returns None when the caller should continue with the full pipeline.
    """
    if text and len(text.strip()) > 0 and len(text.strip()) < min_chunk_size:
        return [{
            "content": text.strip(),
            "chunk_index": 0,
            "page_number": None,
            "section_title": None,
        }]
    if not text or not text.strip():
        return []
    return None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _build_page_map(text: str) -> list[tuple[int, int]]:
    """Map page numbers (1-indexed) to their start offsets in ``text``.

    The "first chunk" before any ``--- PDF ... ---`` boundary is treated
    as header/cover and excluded from the page map.
    """
    pages = _PDF_PAGE_BOUNDARY.split(text)
    page_map: list[tuple[int, int]] = []
    current_pos = 0
    for i, page_text in enumerate(pages[1:], 1):
        page_start = text.find(page_text, current_pos)
        if page_start >= 0:
            page_map.append((i, page_start))
            current_pos = page_start + len(page_text)
    return page_map


def _choose_break(
    text: str, start: int, end: int, min_chunk_size: int
) -> int:
    """Pick the chunk-end position, preferring sentence boundaries.

    Tries ``". "`` backwards within the window first; falls back to the
    next whitespace at-or-after ``end``. Returns the raw ``end`` if neither
    candidate produces a chunk bigger than ``min_chunk_size``.
    """
    sentence_end = text.rfind(". ", start, end)
    if sentence_end > start + min_chunk_size:
        return sentence_end + 1
    word_end = text.find(" ", end)
    if word_end > start + min_chunk_size:
        return word_end
    return end


def _page_number_for_offset(page_map: list[tuple[int, int]], start: int) -> int | None:
    """Return the page that contains the offset, or None if outside any page."""
    for page_num, page_start in page_map:
        if page_start <= start < page_start + _PAGE_WINDOW:
            return page_num
    return None


def _section_title_for_first_chunk(text: str) -> str | None:
    """If the first chunk looks like it has a heading on its first line,
    capture it (legacy behaviour preserved)."""
    lines = text.split("\n")
    if lines and len(lines[0]) < 100:
        return lines[0]
    return None


def _emit_chunks(
    text: str,
    page_map: list[tuple[int, int]],
    chunk_size: int,
    overlap: int,
    min_chunk_size: int,
) -> list[dict]:
    """Greedy chunk emitter. Respects sentence boundaries when the cut
    still leaves a chunk big enough (>= min_chunk_size).
    """
    chunks: list[dict] = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            end = _choose_break(text, start, end, min_chunk_size)

        chunk_text = text[start:end].strip()
        if len(chunk_text) >= min_chunk_size:
            chunk = {
                "content": chunk_text,
                "chunk_index": chunk_index,
                "page_number": _page_number_for_offset(page_map, start),
                "section_title": (
                    _section_title_for_first_chunk(chunk_text)
                    if chunk_index == 0
                    else None
                ),
            }
            chunks.append(chunk)
        start = end - overlap
        chunk_index += 1
    return _renumber_chunks(chunks)


def _renumber_chunks(chunks: list[dict]) -> list[dict]:
    """Re-index chunk_index consecutively starting at 0 (legacy post-pass)."""
    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i
    return chunks

def create_chunks_for_document(
    document_id: int,
    extracted_text: str,
    organization_id: int,
    matter_id: int,
    legal_area: LegalArea | None = None
) -> list[dict]:
    raw_chunks = split_text_into_chunks(extracted_text)

    chunks = []
    for raw_chunk in raw_chunks:
        chunks.append({
            "document_id": document_id,
            "organization_id": organization_id,
            "matter_id": matter_id,
            "content": raw_chunk["content"],
            "chunk_index": raw_chunk["chunk_index"],
            "page_number": raw_chunk["page_number"],
            "section_title": raw_chunk.get("section_title"),
            "legal_area": legal_area
        })

    return chunks
