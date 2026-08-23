-- S5.1 → pgvector migration for law_chunks
--
-- Replaces the JSON-as-text ``embedding`` column with a real
-- ``vector(1536)`` column backed by an HNSW index so
-- ``search_laws_by_embedding`` can do ANN search in SQL instead of
-- pulling every row into Python and running numpy.cosine.
--
-- Idempotent: safe to re-run on a partially-migrated database.

-- 1) Add the vector column if it doesn't exist yet.
ALTER TABLE law_chunks
    ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);

-- 2) Backfill from the legacy JSON column.
UPDATE law_chunks
   SET embedding_vec = (
       SELECT array(
           SELECT (jsonb_array_elements_text(embedding::jsonb))::float
       )::vector(1536)
   )
 WHERE embedding IS NOT NULL
   AND embedding_vec IS NULL;

-- 3) HNSW index for ANN search. ``vector_cosine_ops`` matches the
--    <=> distance operator. ``m=16, ef_construction=64`` are sensible
--    defaults for ~20K rows; bump up for larger corpora.
CREATE INDEX IF NOT EXISTS ix_law_chunks_embedding_vec_hnsw
    ON law_chunks USING hnsw (embedding_vec vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 4) Sanity check: how many rows have the new column populated?
DO $$
DECLARE
    total_rows integer;
    vec_rows integer;
BEGIN
    SELECT COUNT(*) INTO total_rows FROM law_chunks;
    SELECT COUNT(*) INTO vec_rows FROM law_chunks WHERE embedding_vec IS NOT NULL;
    RAISE NOTICE '[033] law_chunks: % total, % with embedding_vec', total_rows, vec_rows;
END $$;
