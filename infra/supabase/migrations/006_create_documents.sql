-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    uploaded_by_user_id INTEGER NOT NULL REFERENCES users(id),
    original_filename VARCHAR(500) NOT NULL,
    storage_path VARCHAR(1000),
    mime_type VARCHAR(100),
    file_size INTEGER,
    file_hash VARCHAR(255),
    status VARCHAR(50) DEFAULT 'uploaded',
    extracted_text TEXT,
    page_count INTEGER,
    detected_document_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_matter ON documents(matter_id);
CREATE INDEX IF NOT EXISTS idx_documents_organization ON documents(organization_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by_user_id);
