-- Document chunks for RAG
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    section_title VARCHAR(500),
    embedding VECTOR(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_matter ON document_chunks(matter_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_organization ON document_chunks(organization_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);
