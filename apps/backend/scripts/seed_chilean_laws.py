"""S5.2 — Indexador de corpus legal chileno.

Lee todos los PDFs de ``apps/backend/laws/``, los divide en chunks y los
indexa en la tabla ``law_chunks`` con sus embeddings. Es idempotente: si
un chunk ya existe (mismo ``law_code`` + ``chunk_index``), lo salta.

USO LOCAL:

    cd apps/backend
    python -m scripts.seed_chilean_laws                    # Re-seed todo
    python -m scripts.seed_chilean_laws --only codigo_trabajo  # Sólo uno
    python -m scripts.seed_chilean_laws --dry-run          # No escribe

USO PROGRAMÁTICO (lo usan el endpoint ``/admin/seed-laws``):

    from scripts.seed_chilean_laws import seed_all, seed_one
    result = seed_all(dry_run=False)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Permitir ejecución tanto como ``python -m scripts.seed_chilean_laws``
# como ``python scripts/seed_chilean_laws.py`` desde ``apps/backend``.
_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.law_chunk import LawChunk  # noqa: E402
from app.models.legal_area import get_legal_area_from_law_code  # noqa: E402
from app.services.embeddings import get_embedding_provider  # noqa: E402

logger = logging.getLogger("lilian.seed_laws")


# Metadata por defecto para cada PDF del directorio ``laws/``. El
# ``code`` se usa como ``law_code`` y para deduplicar.
LAWS_METADATA: dict[str, dict[str, str]] = {
    "codigo_trabajo": {
        "name": "Código del Trabajo de Chile",
        "description": "DFL 1 de 2003 - Regula las relaciones laborales.",
    },
    "codigo_civil": {
        "name": "Código Civil de Chile",
        "description": "Regula las relaciones de derecho privado.",
    },
    "codigo_comercio": {
        "name": "Código de Comercio de Chile",
        "description": "Regula los actos de comercio.",
    },
    "codigo_penal": {
        "name": "Código Penal de Chile",
        "description": "Define los delitos y sus penas.",
    },
    "codigo_procedimiento_penal": {
        "name": "Código de Procedimiento Penal",
        "description": "Regula el procedimiento penal.",
    },
    "codigo_organico_tribunales": {
        "name": "Código Orgánico de Tribunales",
        "description": "Ley 18.782 - Orgánica de Tribunales.",
    },
    "codigo_aguas": {
        "name": "Código de Aguas",
        "description": "Regula las aguas.",
    },
    "ley_proteccion_consumidor": {
        "name": "Ley 19.496 - Protección de los Derechos de los Consumidores",
        "description": "Ley de protección al consumidor.",
    },
    "ley_tribunales_familia": {
        "name": "Ley 19.968 - Tribunales de Familia",
        "description": "Crea los Tribunales de Familia.",
    },
    "ley_bancos": {
        "name": "Ley 18.248 - Ley de Bancos",
        "description": "Regula bancos e instituciones financieras.",
    },
    "ley_quiebras": {
        "name": "Ley 1.552 - Ley de Quiebras",
        "description": "Regula el procedimiento de quiebra.",
    },
    "ley_medicinas": {
        "name": "Ley 1.853 - Ley de Medicinas",
        "description": "Regula la producción y comercio de medicinas.",
    },
    "estatuto_administrativo": {
        "name": "DFL 1.122 - Estatuto Administrativo",
        "description": "Regula las relaciones de empleo público.",
    },
    "estatuto_seguridad_social": {
        "name": "DFL 725 - Estatuto de la Seguridad Social",
        "description": "Regula la seguridad social.",
    },
    "DFL-1_30-MAY-2000": {
        "name": "DFL 1 de 30 de mayo de 2000",
        "description": "DFL de seguros y fondos de pensiones.",
    },
}

DEFAULT_LAWS_DIR = _BACKEND_DIR / "laws"


@dataclass
class SeedReport:
    """Resumen de un seed run, suitable para serializar a JSON."""

    laws_found: list[str] = field(default_factory=list)
    laws_skipped: list[str] = field(default_factory=list)
    chunks_inserted: int = 0
    chunks_skipped_existing: int = 0
    chunks_failed: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "laws_found": self.laws_found,
            "laws_skipped": self.laws_skipped,
            "chunks_inserted": self.chunks_inserted,
            "chunks_skipped_existing": self.chunks_skipped_existing,
            "chunks_failed": self.chunks_failed,
            "errors": self.errors,
            "dry_run": self.dry_run,
        }


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def _split_into_articles(text: str) -> list[dict]:
    """Detecta límites de artículos en leyes chilenas.

    Devuelve ``[{number, content}, ...]``. Si ningún patrón hace match,
    retorna lista vacía y el caller debe recurrir a chunking genérico.
    """
    patterns = [
        r"Art[ií]culo\s+(\d+[A-Z]?)\s*[-–—]?\s*(.*?)(?=Art[ií]culo\s+\d|$)",
        r"Art\.\s*(\d+[A-Z]?)\s*[-–—]?\s*(.*?)(?=Art\.\s*\d|$)",
        r"^(\d+)\.\s+(.*?)(?=^\d+\.\s+|$)",
    ]
    articles: list[dict] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE | re.DOTALL):
            article_num = match.group(1)
            content = match.group(2).strip()
            if len(content) > 20:
                articles.append({"number": article_num, "content": content})
        if articles:
            return articles
    return articles


def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Chunking genérico por oración cuando no hay artículos detectables."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if end < len(text):
            last_period = chunk.rfind(". ")
            last_newline = chunk.rfind("\n")
            cut_point = max(last_period, last_newline)
            if cut_point > chunk_size - 500:
                chunk = chunk[: cut_point + 1]
                end = start + cut_point + 1
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if c]


def _existing_index(db, law_code: str) -> set[int]:
    """Devuelve los ``chunk_index`` ya existentes para ``law_code``."""
    rows = (
        db.query(LawChunk.chunk_index)
        .filter(LawChunk.law_code == law_code)
        .all()
    )
    return {row[0] for row in rows}


def _process_pdf(pdf_path: Path, law_code: str) -> list[dict]:
    """Extrae texto del PDF y lo divide en chunks estructurados."""
    from app.services.document_processor import extract_text_from_file

    raw = extract_text_from_file(str(pdf_path), "application/pdf")
    if not raw or len(raw) < 100:
        raise ValueError(
            f"No se pudo extraer texto de {pdf_path.name} "
            f"({len(raw) if raw else 0} chars)"
        )

    cleaned = _clean_text(raw)
    articles = _split_into_articles(cleaned)
    if articles:
        return [
            {
                "index": i,
                "content": f"Artículo {a['number']}: {a['content']}",
                "article_number": a["number"],
            }
            for i, a in enumerate(articles)
        ]

    text_chunks = _chunk_text(cleaned)
    return [
        {
            "index": i,
            "content": chunk,
            "article_number": None,
        }
        for i, chunk in enumerate(text_chunks)
    ]


def seed_law(
    *,
    law_code: str,
    pdf_path: Path,
    law_name: str,
    db,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Indexa una ley específica en ``law_chunks``.

    Retorna ``(inserted, skipped_existing, failed)``.
    """
    provider = get_embedding_provider()
    legal_area = get_legal_area_from_law_code(law_code)
    legal_area_value = (
        legal_area.value if hasattr(legal_area, "value") else str(legal_area)
    )

    try:
        chunks = _process_pdf(pdf_path, law_code)
    except Exception as exc:
        logger.exception("seed_law %s: process failed", law_code)
        raise

    if not chunks:
        logger.warning("seed_law %s: no chunks produced", law_code)
        return 0, 0, 0

    existing = set() if dry_run else _existing_index(db, law_code)
    inserted = 0
    skipped = 0
    failed = 0

    for chunk in chunks:
        idx = chunk["index"]
        if idx in existing:
            skipped += 1
            continue
        try:
            embedding = provider.generate_embedding(chunk["content"])
            embedding_str = json.dumps(embedding)
            if not dry_run:
                row = LawChunk(
                    law_code=law_code,
                    law_name=law_name,
                    article_number=chunk.get("article_number"),
                    chunk_index=idx,
                    content=chunk["content"],
                    embedding=embedding_str,
                    legal_area=legal_area_value,
                    chunk_metadata={
                        "indexed_from": "seed_chilean_laws",
                        "chunk_size": len(chunk["content"]),
                    },
                )
                db.add(row)
            inserted += 1
        except Exception as exc:
            logger.warning(
                "seed_law %s chunk %s failed: %s",
                law_code, idx, exc,
            )
            failed += 1

    if not dry_run:
        db.commit()

    logger.info(
        "seed_law %s: %d inserted, %d skipped, %d failed",
        law_code, inserted, skipped, failed,
    )
    return inserted, skipped, failed


def _resolve_laws(
    laws_dir: Path,
    only: str | None,
) -> list[tuple[str, Path, str]]:
    """Devuelve una lista ``(law_code, pdf_path, law_name)`` a procesar."""
    if not laws_dir.exists():
        raise FileNotFoundError(f"Directorio de leyes no existe: {laws_dir}")

    candidates: list[tuple[str, Path, str]] = []
    for pdf_path in sorted(laws_dir.glob("*.pdf")):
        base_name = pdf_path.stem.lower()
        # Aliases for backward compatibility
        meta = LAWS_METADATA.get(base_name)
        if meta is None and base_name.startswith("dfl-"):
            meta = LAWS_METADATA.get("DFL-1_30-MAY-2000")
        if meta is None:
            meta = {
                "name": pdf_path.stem.replace("_", " ").title(),
                "description": "",
            }
        law_code = base_name
        candidates.append((law_code, pdf_path, meta["name"]))

    if only:
        only = only.lower()
        candidates = [c for c in candidates if c[0] == only]
        if not candidates:
            raise ValueError(f"No se encontró PDF para {only} en {laws_dir}")

    return candidates


def seed_all(
    laws_dir: Path | str | None = None,
    only: str | None = None,
    dry_run: bool = False,
) -> SeedReport:
    """Indexa todos los PDFs del directorio de leyes.

    Returns:
        ``SeedReport`` con el resumen de la operación.
    """
    laws_dir = Path(laws_dir) if laws_dir else DEFAULT_LAWS_DIR
    report = SeedReport(dry_run=dry_run)

    try:
        targets = _resolve_laws(laws_dir, only)
    except FileNotFoundError as exc:
        report.errors.append(str(exc))
        return report
    except ValueError as exc:
        report.errors.append(str(exc))
        return report

    if not targets:
        report.errors.append(f"No hay PDFs en {laws_dir}")
        return report

    # Ensure schema exists (cheap when tables already exist).
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        for law_code, pdf_path, law_name in targets:
            report.laws_found.append(law_code)
            try:
                ins, skip, fail = seed_law(
                    law_code=law_code,
                    pdf_path=pdf_path,
                    law_name=law_name,
                    db=db,
                    dry_run=dry_run,
                )
                report.chunks_inserted += ins
                report.chunks_skipped_existing += skip
                report.chunks_failed += fail
            except Exception as exc:
                report.chunks_failed += 1
                report.errors.append(f"{law_code}: {exc}")
    finally:
        db.close()

    return report


def _iter_law_summaries(db) -> Iterable[dict]:
    """Resumen por ley indexada (cuántos chunks, cuándo)."""
    from sqlalchemy import func

    rows = (
        db.query(
            LawChunk.law_code,
            LawChunk.law_name,
            func.count(LawChunk.id).label("chunks"),
            func.min(LawChunk.created_at).label("first_indexed"),
            func.max(LawChunk.created_at).label("last_indexed"),
        )
        .group_by(LawChunk.law_code, LawChunk.law_name)
        .all()
    )
    return [
        {
            "law_code": r.law_code,
            "law_name": r.law_name,
            "chunks": r.chunks,
            "first_indexed_at": r.first_indexed.isoformat() if r.first_indexed else None,
            "last_indexed_at": r.last_indexed.isoformat() if r.last_indexed else None,
        }
        for r in rows
    ]


def get_seed_status() -> dict:
    """Devuelve el estado actual del corpus indexado."""
    db = SessionLocal()
    try:
        summaries = list(_iter_law_summaries(db))
        total_chunks = sum(s["chunks"] for s in summaries)
        return {
            "total_laws": len(summaries),
            "total_chunks": total_chunks,
            "laws": summaries,
        }
    finally:
        db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="S5.2 — Indexador del corpus legal chileno."
    )
    parser.add_argument(
        "--laws-dir",
        type=str,
        default=str(DEFAULT_LAWS_DIR),
        help="Directorio con los PDFs (default: apps/backend/laws/)",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Sólo re-seed de esta ley (ej: codigo_trabajo)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No escribe en la base de datos, sólo reporta.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    laws_dir = Path(args.laws_dir)
    report = seed_all(
        laws_dir=laws_dir,
        only=args.only,
        dry_run=args.dry_run,
    )
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    if report.errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
