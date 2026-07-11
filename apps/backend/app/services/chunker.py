from typing import List, Optional
import re


def split_text_into_chunks(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    min_chunk_size: int = 200
) -> List[dict]:
    if not text or len(text.strip()) < min_chunk_size:
        if text and len(text.strip()) > 0:
            return [{
                "content": text.strip(),
                "chunk_index": 0,
                "page_number": None,
                "section_title": None
            }]
        return []

    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    chunks = []
    start = 0
    chunk_index = 0

    page_pattern = re.compile(r'--- PDF.*?---', re.IGNORECASE)
    pages = page_pattern.split(text)

    current_pos = 0
    page_map = []
    for i, page_text in enumerate(pages[1:], 1):
        page_start = text.find(page_text, current_pos)
        if page_start >= 0:
            page_map.append((i, page_start))
            current_pos = page_start + len(page_text)

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            nearest_break = text.rfind('. ', start, end)
            if nearest_break > start + min_chunk_size:
                end = nearest_break + 1
            else:
                nearest_break = text.find(' ', end)
                if nearest_break > start + min_chunk_size:
                    end = nearest_break

        chunk_text = text[start:end].strip()

        if len(chunk_text) >= min_chunk_size:
            page_num = None
            for pnum, pstart in page_map:
                if pstart <= start < pstart + 500:
                    page_num = pnum
                    break

            section = None
            if chunk_index == 0:
                lines = chunk_text.split('\n')
                if lines and len(lines[0]) < 100:
                    section = lines[0]

            chunks.append({
                "content": chunk_text,
                "chunk_index": chunk_index,
                "page_number": page_num,
                "section_title": section
            })

        start = end - overlap
        chunk_index += 1

    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i

    return chunks


def create_chunks_for_document(document_id: int, extracted_text: str, organization_id: int, matter_id: int) -> List[dict]:
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
            "section_title": raw_chunk.get("section_title")
        })

    return chunks
