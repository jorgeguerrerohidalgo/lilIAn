-- Document Analysis table for Harvey-style document understanding
CREATE TABLE IF NOT EXISTS document_analyses (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Document type detected
    document_type VARCHAR(100),

    -- Structured data extracted (JSON)
    participants JSONB DEFAULT '[]',
    financial_terms JSONB DEFAULT '{}',
    obligations JSONB DEFAULT '[]',
    clauses_by_type JSONB DEFAULT '{}',
    unusual_clauses JSONB DEFAULT '[]',
    legal_references JSONB DEFAULT '[]',

    -- Indexed content for search
    indexed_content TEXT,

    -- Metadata
    analysis_metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_document_analyses_document_id ON document_analyses(document_id);
CREATE INDEX IF NOT EXISTS idx_document_analyses_organization_id ON document_analyses(organization_id);
CREATE INDEX IF NOT EXISTS idx_document_analyses_document_type ON document_analyses(document_type);

-- Add analysis relationship to documents table (optional column for quick access)
-- ALTER TABLE documents ADD COLUMN IF NOT EXISTS has_analysis BOOLEAN DEFAULT FALSE;
