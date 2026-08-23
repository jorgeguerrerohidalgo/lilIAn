-- S5.1 → pgvector migration for document_chunks
--
-- Mirrors 033 for law_chunks: replaces the JSON-as-text ``embedding``
-- column with a real ``vector(1536)`` column + HNSW index so ANN
-- search happens in SQL instead of pulling every chunk into Python
-- and running numpy.cosine. Also fixes the dim-mismatch silent-fail
-- that was making the chat return "no documents found" when a
-- matter had any 512-dim chunk mixed in with 1536-dim ones.

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);

-- Backfill from legacy JSON. The 512-dim chunks (mixed from older
-- indexer runs) are skipped — pgvector's vector(1536) column cannot
-- store them, and re-running the document processor at 1536 dims is
-- the only path forward for those rows.
UPDATE document_chunks
   SET embedding_vec = (
       SELECT array(
           SELECT (jsonb_array_elements_text(embedding::jsonb))::float
       )::vector(1536)
   )
 WHERE embedding IS NOT NULL
   AND jsonb_array_length(embedding::jsonb) = 1536
   AND embedding_vec IS NULL;

-- HNSW index — same defaults as law_chunks (m=16, ef_construction=64).
CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vec_hnsw
    ON document_chunks USING hnsw (embedding_vec vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Drop the legacy Text column now that the data is migrated. New
-- code writes to ``embedding_vec`` directly.
ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding;
