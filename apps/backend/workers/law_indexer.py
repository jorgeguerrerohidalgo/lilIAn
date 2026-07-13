"""
Script para indexar leyes chilenas en el vector store.

Uso:
    python -m workers.law_indexer /path/to/laws/directory

El directorio debe contener PDFs de leyes con nombre significativo, ej:
    - codigo_trabajo.pdf
    - codigo_civil.pdf
    - ley_proteccion_consumidor.pdf
"""

import os
import sys
import json
import re

sys.path.insert(0, '/app')

from app.core.database import SessionLocal, engine
from app.models.law_chunk import LawChunk
from app.models.legal_area import get_legal_area_from_law_code
from app.services.embeddings import get_embedding_provider
from app.services.document_processor import extract_text_from_file


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
    """Limpia texto extraído de PDF."""
    # Remover múltiples espacios
    text = re.sub(r'\s+', ' ', text)
    # Remover líneas vacías múltiples
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def split_into_articles(text: str) -> list:
    """Intenta dividir el texto en artículos."""
    articles = []

    # Patrones comunes para artículos en leyes chilenas
    patterns = [
        r'Artículo\s+(\d+[A-Z]?)\s*[-–—]?\s*(.*?)(?=Artículo\s+\d|$)',
        r'Art\.\s*(\d+[A-Z]?)\s*[-–—]?\s*(.*?)(?=Art\.\s*\d|$)',
        r'^(\d+)\.\s+(.*?)(?=^\d+\.\s+|$)',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)
        for match in matches:
            article_num = match.group(1)
            content = match.group(2).strip()
            if len(content) > 20:  # Filtrar artículos muy cortos
                articles.append({
                    "number": article_num,
                    "content": content
                })

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

    if articles:
        # Usar artículos como chunks
        chunks = []
        for i, article in enumerate(articles):
            chunks.append({
                "index": i,
                "content": f"Artículo {article['number']}: {article['content']}",
                "article_number": article['number']
            })
    else:
        # Usar chunks genéricos
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


def index_law_chunks(law_code: str, law_name: str, chunks: list, db) -> int:
    """Indexa los chunks de una ley en la base de datos."""
    embedding_provider = get_embedding_provider()
    legal_area = get_legal_area_from_law_code(law_code)

    indexed_count = 0
    for chunk_data in chunks:
        try:
            # Generar embedding
            embedding = embedding_provider.generate_embedding(chunk_data["content"])
            embedding_str = json.dumps(embedding)

            # Crear chunk en la base de datos
            # Usar el valor string del enum para evitar problemas de case
            law_chunk = LawChunk(
                law_code=law_code,
                law_name=law_name,
                article_number=chunk_data.get("article_number"),
                chunk_index=chunk_data["index"],
                content=chunk_data["content"],
                embedding=embedding_str,
                legal_area=legal_area.value if hasattr(legal_area, 'value') else legal_area,
                chunk_metadata={
                    "indexed_from": "law_indexer",
                    "chunk_size": len(chunk_data["content"])
                }
            )
            db.add(law_chunk)
            indexed_count += 1

        except Exception as e:
            print(f"Error indexing chunk {chunk_data['index']}: {e}")
            continue

    db.commit()
    return indexed_count


def main(laws_directory: str):
    """Procesa todas las leyes en el directorio."""
    print(f"Processing laws from: {laws_directory}")

    # Crear tablas si no existen
    from app.core.database import Base
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    embedding_provider = get_embedding_provider()

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
