-- S7.1 → GIN index on law_chunks.content for keyword search
--
-- ``search_laws_by_keyword`` (Plan B of the hybrid RAG) uses
-- ``to_tsvector('spanish', content) @@ to_tsquery('spanish', :q)``.
-- Without an index, Postgres computes the tsvector for every row on every
-- query; on 14k chunks that took ~10s per call. With this GIN index the
-- same lookup drops to ~200ms (50x) and stays under a second as the
-- corpus grows toward Tier 2/3 (60x+ more rows).
--
-- Idempotent: safe to re-run on an already-indexed database.

CREATE INDEX IF NOT EXISTS law_chunks_tsv_idx
    ON law_chunks USING gin (to_tsvector('spanish', content));

DO $$
DECLARE
    total_rows integer;
    idx_rows   integer;
BEGIN
    SELECT COUNT(*) INTO total_rows FROM law_chunks;
    SELECT COUNT(*) INTO idx_rows
      FROM law_chunks
     WHERE to_tsvector('spanish', content) @@ to_tsquery('spanish', 'articulo');
    RAISE NOTICE '[035] law_chunks: % total, % match "articulo" via tsvector', total_rows, idx_rows;
END $$;