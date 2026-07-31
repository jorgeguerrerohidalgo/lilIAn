-- Law chunks for RAG segmented by legal area
CREATE TABLE IF NOT EXISTS law_chunks (
    id SERIAL PRIMARY KEY,
    law_code VARCHAR(100) NOT NULL,
    law_name VARCHAR(500) NOT NULL,
    article_number VARCHAR(50),
    chapter_title VARCHAR(500),
    section_title VARCHAR(500),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    legal_area VARCHAR(50) NOT NULL DEFAULT 'other',
    chunk_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_law_chunks_law_code ON law_chunks(law_code);
CREATE INDEX IF NOT EXISTS idx_law_chunks_legal_area ON law_chunks(legal_area);
CREATE INDEX IF NOT EXISTS idx_law_chunks_embedding ON law_chunks USING ivfflat (embedding vector_cosine_ops);
