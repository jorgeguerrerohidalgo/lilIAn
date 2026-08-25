"""
Script para indexar leyes chilenas en el vector store.

Uso:
    python -m workers.law_indexer /path/to/laws/directory

El directorio debe contener PDFs de leyes con nombre significativo, ej:
    - codigo_trabajo.pdf
    - codigo_civil.pdf
    - ley_proteccion_consumidor.pdf
"""

import json
import os
import re
import sys

sys.path.insert(0, '/app')

from app.core.database import SessionLocal, engine
from app.models.law_chunk import LawChunk
from app.models.legal_area import get_legal_area_from_law_code
from app.services.document_processor import extract_text_from_file
from app.services.embeddings import get_embedding_provider

LAWS_METADATA = {
    # Códigos principales
    "codigo_trabajo": {
        "name": "Código del Trabajo de Chile",
        "code": "codigo_trabajo",
        "description": "DFL 1 de 2003 - Regula las relaciones laborales"
    },
    "codigo_civil": {
        "name": "Código Civil de Chile",
        "code": "codigo_civil",
        "description": "Regula las relaciones de derecho privado"
    },
    "codigo_comercio": {
        "name": "Código de Comercio de Chile",
        "code": "codigo_comercio",
        "description": "Regula los actos de comercio"
    },
    "codigo_penal": {
        "name": "Código Penal de Chile",
        "code": "codigo_penal",
        "description": "Define los delitos y sus penas"
    },
    "codigo_procedimiento_penal": {
        "name": "Código de Procedimiento Penal",
        "code": "codigo_procedimiento_penal",
        "description": "DL 830 de 1974 - Regula el procedimiento penal"
    },
    "codigo_organico_tribunales": {
        "name": "Código Orgánico de Tribunales",
        "code": "codigo_organico_tribunales",
        "description": "Ley 18782 - Orgánica de Tribunales"
    },
    "codigo_aguas": {
        "name": "Código de Aguas",
        "code": "codigo_aguas",
        "description": "Decreto 374 de 1934 - Regula las aguas"
    },
    # Leyes por área
    "ley_proteccion_consumidor": {
        "name": "Ley 18.916 - Protección de los Derechos de los Consumidores",
        "code": "ley_proteccion_consumidor",
        "description": "Ley de protección al consumidor"
    },
    "ley_tribunales_familia": {
        "name": "Ley 19.968 - Tribunales de Familia",
        "code": "ley_tribunales_familia",
        "description": "Ley que crea los Tribunales de Familia"
    },
    "ley_bancos": {
        "name": "Ley 18.248 - Ley de Bancos",
        "code": "ley_bancos",
        "description": "Regula bancos e instituciones financieras"
    },
    "ley_quiebras": {
        "name": "Ley 1.552 - Ley de Quiebras",
        "code": "ley_quiebras",
        "description": "Regula elprocedimiento de quiebra"
    },
    "ley_medicinas": {
        "name": "Ley 1.853 - Ley de Medicines",
        "code": "ley_medicinas",
        "description": "Regula la producción y comercio de medicines"
    },
    "estatuto_administrativo": {
        "name": "DFL 1.122 - Estatuto Administrativo",
        "code": "estatuto_administrativo",
        "description": "Regula las relaciones de empleo público"
    },
    "estatuto_seguridad_social": {
        "name": "DFL 725 - Estatuto de la Seguridad Social",
        "code": "estatuto_seguridad_social",
        "description": "Regula la seguridad social"
    },
    # Leyes adicionales (para compatibilidad)
    "ley_menores": {
        "name": "Ley 16.618 - Ley de Menores",
        "code": "ley_16618",
        "description": "Ley de protección de menores"
    },
    "ley_sistema_filiacion": {
        "name": "Ley 19.585 - Sistema de filiación",
        "code": "ley_19585",
        "description": "Ley que modifica el sistema de filiación"
    },
}


def clean_text(text: str) -> str:
    """Limpia texto extraído de PDF preservando saltos de línea e indents.

    S5.1: replaces the old version that collapsed all whitespace via
    ``\\s+`` (which also matched newlines). ``split_into_articles``
    relies on the short-indent header pattern ``\\n {5}Art\\.\\s+\\d``
    that the PDF extractor emits — the leading spaces on the line
    after a newline ARE the article-header indent and must survive
    cleanup, otherwise everything collapses into one line.
    """
    # Collapse runs of 10+ spaces/tabs (long indents that aren't
    # meaningful for the header pattern). Keep runs of 1-9.
    text = re.sub(r"[ \t]{10,}", " ", text)
    # Trim spaces BEFORE newlines only — leave the leading indent
    # of the next line alone so the header regex can see it.
    text = re.sub(r" +\n", "\n", text)
    # Collapse blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_articles(text: str) -> list:
    """Divide el texto en artículos completos, sin cortar sub-ítems.

    S5.1: replaces the previous lazy-match approach that captured only
    the article header. Anchors on header **positions** instead:

      1. Find every ``Art. N`` / ``Artículo N`` whose preceding
         indent is the article-header column. Different PDFs use
         different column widths: the Código del Trabajo emits 5
         spaces; most of the other PDFs (Código de Aguas, Ley de
         Bancos, ...) emit 4. Sub-ítems like ``Art. 1, N° 1 a)``
         live at 30+ spaces and so are filtered out.

      2. Slice the text between consecutive headers. Each slice
         becomes one chunk containing header + body.

      3. Dedup by canonical article number: ``Art. 159`` and
         ``Artículo 159`` in the same text collapse to one chunk.

    Why this matters: the old regex returned chunks like
    ``"Artículo 159: . El contrato de trabajo terminará..."`` (83
    chars — just the header). The RAG couldn't actually answer
    anything because the body lived in a sibling chunk. With position
    slicing, each chunk has the full article text.
    """
    # 4 OR 5 spaces — different PDFs use different column widths.
    # The Código del Trabajo uses 5; most others use 4. Sub-ítems
    # at 30+ spaces are filtered by the {4,5} cap.
    header_re = re.compile(
        r"\n[ ]{4,5}"
        r"Art(?:[ií]culo|\.)\s+"
        r"(\d+)"                # canonical article number
        r"(?:[\.º°][a-zñ]*)?"
        r"(?:\s+(?:bis|ter|quater))?"
        r"(?:\s+N[°ºo]?\s*\d+(?:\s*[a-z])?)?"
    )
    matches = list(header_re.finditer(text))

    articles: list[dict] = []
    seen_numbers: set[str] = set()
    for i, m in enumerate(matches):
        number = m.group(1)
        if number in seen_numbers:
            continue
        start = m.start() + 1
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk_text = text[start:end].strip()
        if len(chunk_text) < 100:
            continue
        seen_numbers.add(number)
        articles.append({"number": number, "content": chunk_text})

    return articles


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list:
    """Divide texto en chunks con solapamiento."""
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]

        # Intentar cortar en límite de oración
        if end < text_length:
            last_period = chunk.rfind('. ')
            last_newline = chunk.rfind('\n')
            cut_point = max(last_period, last_newline)
            if cut_point > chunk_size - 500:
                chunk = chunk[:cut_point + 1]
                end = start + cut_point + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return chunks


def process_law_pdf(file_path: str, law_code: str) -> dict:
    """Procesa un PDF de ley y retorna los chunks."""
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    # Extraer texto
    extracted_text = extract_text_from_file(file_path, "application/pdf")
    if not extracted_text or len(extracted_text) < 100:
        return {"error": "No text extracted or insufficient text"}

    cleaned_text = clean_text(extracted_text)

    # Intentar dividir en artículos
    articles = split_into_articles(cleaned_text)

    # Heuristic: if split_into_articles found very few articles
    # (suggesting header recognition failed) OR every article is huge
    # (the header regex merged the whole document into one or two
    # mega-chunks that won't fit an LLM context window), fall back to
    # the generic chunker. Empirically: PDFs whose article headers
    # match the 5-space ``Art. N.o`` indent return ~hundreds of
    # medium-sized chunks; PDFs whose layout differs return 1–5 chunks
    # that are tens of thousands of characters long.
    avg_article_size = (
        sum(len(a["content"]) for a in articles) / len(articles)
        if articles else 0
    )
    use_article_chunks = (
        articles
        and len(articles) >= 10
        and avg_article_size <= 20_000
    )

    if use_article_chunks:
        # Usar artículos como chunks
        chunks = []
        for i, article in enumerate(articles):
            chunks.append({
                "index": i,
                "content": f"Artículo {article['number']}: {article['content']}",
                "article_number": article['number']
            })
    else:
        # Usar chunks genéricos (fallback)
        text_chunks = chunk_text(cleaned_text)
        chunks = [{
            "index": i,
            "content": chunk,
            "article_number": None
        } for i, chunk in enumerate(text_chunks)]

    return {
        "law_code": law_code,
        "total_chunks": len(chunks),
        "chunks": chunks
    }


def index_law_chunks(law_code: str, law_name: str, chunks: list, db, batch_size: int = 50, sleep_between_batches: float = 2.0) -> int:
    """Indexa los chunks de una ley en la base de datos usando batching.

    Process chunks in batches of ``batch_size`` so we make at most
    ``ceil(len(chunks)/batch_size)`` requests to the embedding provider
    instead of one-per-chunk. Sleeps ``sleep_between_batches`` seconds
    between batches so we stay well under the OpenAI tier-1 rate limit
    (~60 req/min) even on accounts with strict per-minute quotas.

    Chunks are padded to >=2000 chars before being sent to OpenAI so
    the embeddings always come back at 1536 dims. The padding trick
    matches what chat queries already do — without it, a batch of
    short articles silently returns 512-dim vectors that don't fit
    the law_chunks.embedding_vec vector(1536) column.

    Note: when the embedding provider fails (e.g. 429), it silently
    falls back to dummy embeddings. The caller MUST check that the
    resulting embeddings look real (e.g. non-deterministic across runs)
    before trusting the index. We don't fail loud here because the
    existing provider contract returns a list-of-embeddings on success
    or fallback indistinguishably.
    """
    import time

    embedding_provider = get_embedding_provider()
    legal_area = get_legal_area_from_law_code(law_code)

    SHORT_PAD_THRESHOLD = 2000

    def _pad_for_1536(text: str) -> str:
        if len(text) >= SHORT_PAD_THRESHOLD:
            return text
        return text + " " * (SHORT_PAD_THRESHOLD - len(text))

    indexed_count = 0
    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start:batch_start + batch_size]
        texts = [_pad_for_1536(c["content"]) for c in batch]
        try:
            embeddings = embedding_provider.generate_embeddings(texts)
        except Exception as e:
            print(f"Error indexing batch starting at chunk {batch_start}: {e}")
            continue

        for chunk_data, embedding in zip(batch, embeddings):
            law_chunk = LawChunk(
                law_code=law_code,
                law_name=law_name,
                article_number=chunk_data.get("article_number"),
                chunk_index=chunk_data["index"],
                content=chunk_data["content"],
                embedding_vec=embedding,
                legal_area=legal_area.value if hasattr(legal_area, 'value') else legal_area,
                chunk_metadata={
                    "indexed_from": "law_indexer",
                    "chunk_size": len(chunk_data["content"])
                }
            )
            db.add(law_chunk)
            indexed_count += 1

        # Throttle between batches so OpenAI's per-minute rate limit
        # doesn't fire on long PDFs. With batch_size=50 and 14 laws at
        # ~300 chunks each, the total run makes ~84 calls over ~3 min.
        if batch_start + batch_size < len(chunks):
            time.sleep(sleep_between_batches)

    db.commit()
    return indexed_count


def main(laws_directory: str):
    """Procesa todas las leyes en el directorio."""
    print(f"Processing laws from: {laws_directory}")

    # Crear tablas si no existen
    from app.core.database import Base
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    get_embedding_provider()

    try:
        # Procesar cada archivo en el directorio
        for filename in os.listdir(laws_directory):
            if not filename.endswith('.pdf'):
                continue

            file_path = os.path.join(laws_directory, filename)
            print(f"\nProcessing: {filename}")

            # Extraer código de ley del nombre del archivo
            base_name = os.path.splitext(filename)[0].lower()
            law_meta = LAWS_METADATA.get(base_name, {
                "name": filename.replace('.pdf', '').replace('_', ' ').title(),
                "code": base_name
            })

            # Procesar PDF
            result = process_law_pdf(file_path, law_meta["code"])

            if "error" in result:
                print(f"  Error: {result['error']}")
                continue

            print(f"  Found {result['total_chunks']} chunks")

            # Indexar chunks
            indexed = index_law_chunks(
                law_code=law_meta["code"],
                law_name=law_meta["name"],
                chunks=result["chunks"],
                db=db
            )
            print(f"  Indexed {indexed} chunks successfully")

    finally:
        db.close()
        print("\nIndexing complete!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m workers.law_indexer /path/to/laws/directory")
        sys.exit(1)

    laws_dir = sys.argv[1]
    main(laws_dir)
