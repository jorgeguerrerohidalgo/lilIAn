"""
Script de migración para agregar legal_area a chunks existentes.

Uso:
    python -m migrations.add_legal_area

Este script:
1. Actualiza law_chunks con legal_area basado en law_code
2. Actualiza document_chunks con legal_area basado en matter.matter_type
"""
import sys
sys.path.insert(0, '/app')

from app.core.database import SessionLocal, engine
from app.models.law_chunk import LawChunk
from app.models.document_chunk import DocumentChunk
from app.models.matter import Matter
from app.models.legal_area import (
    LegalArea,
    LAW_CODE_TO_LEGAL_AREA,
    MATTER_TYPE_TO_LEGAL_AREA,
    get_legal_area_from_law_code
)


def migrate_law_chunks():
    """Actualiza legal_area en law_chunks basado en law_code."""
    db = SessionLocal()
    try:
        chunks = db.query(LawChunk).filter(LawChunk.legal_area.is_(None)).all()
        updated = 0

        for chunk in chunks:
            legal_area = get_legal_area_from_law_code(chunk.law_code)
            chunk.legal_area = legal_area
            updated += 1

        db.commit()
        print(f"LawChunks actualizados: {updated}")
        return updated
    finally:
        db.close()


def migrate_document_chunks():
    """Actualiza legal_area en document_chunks basado en matter.matter_type."""
    db = SessionLocal()
    try:
        # Obtener todos los chunks sin legal_area
        chunks = db.query(DocumentChunk).filter(DocumentChunk.legal_area.is_(None)).all()
        updated = 0
        errors = 0

        for chunk in chunks:
            try:
                matter = db.query(Matter).filter(Matter.id == chunk.matter_id).first()
                if matter and matter.matter_type:
                    legal_area = MATTER_TYPE_TO_LEGAL_AREA.get(
                        matter.matter_type.value,
                        LegalArea.OTHER
                    )
                    chunk.legal_area = legal_area
                    updated += 1
                else:
                    chunk.legal_area = LegalArea.OTHER
                    updated += 1
            except Exception as e:
                errors += 1
                print(f"Error en chunk {chunk.id}: {e}")

        db.commit()
        print(f"DocumentChunks actualizados: {updated}, errores: {errors}")
        return updated
    finally:
        db.close()


def main():
    print("Iniciando migración de legal_area...")
    print("=" * 50)

    # Crear tablas si no existen (para entornos nuevos)
    from app.core.database import Base
    Base.metadata.create_all(bind=engine)

    print("\n1. Migrando law_chunks...")
    migrate_law_chunks()

    print("\n2. Migrando document_chunks...")
    migrate_document_chunks()

    print("\n" + "=" * 50)
    print("Migración completada.")


if __name__ == "__main__":
    main()
