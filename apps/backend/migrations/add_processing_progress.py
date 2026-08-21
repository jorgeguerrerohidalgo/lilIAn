"""Migration: add processing_step + processing_progress to documents.

The user reported on 20-aug-2026 that the Documentos tab shows just
``Procesando...`` with no indication of which step the pipeline is
in or how long remains. Fix: track current step name + percent in
two new columns so the UI can poll and show a stepper.

Steps (sequential, percentages approximate):
  - extracting_text  (10-40%)
  - recording_pages  (40-45%)
  - generating_chunks (45-90%)
  - indexing         (90-95%)
  - classifying      (95-99%, runs in background task)
  - done             (100%)
"""
import sys

sys.path.insert(0, "/app")

from sqlalchemy import text

from app.core.database import SessionLocal, engine


def main() -> None:
    print("[add_processing_progress] starting", flush=True)
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE documents "
            "ADD COLUMN IF NOT EXISTS processing_step VARCHAR(50)"
        ))
        conn.execute(text(
            "ALTER TABLE documents "
            "ADD COLUMN IF NOT EXISTS processing_progress INTEGER"
        ))
    print("  ALTER TABLE documents OK", flush=True)
    db = SessionLocal()
    cur = db.execute(text(
        "SELECT column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_name = 'documents' "
        "AND column_name IN ('processing_step', 'processing_progress')"
    ))
    for row in cur:
        print(f"  {row[0]}: {row[1]}", flush=True)
    db.close()
    print("[add_processing_progress] done", flush=True)


if __name__ == "__main__":
    main()