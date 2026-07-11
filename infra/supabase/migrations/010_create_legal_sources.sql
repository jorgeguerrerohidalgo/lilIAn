-- Legal sources table
CREATE TABLE IF NOT EXISTS legal_sources (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    source_type VARCHAR(100) NOT NULL,
    origin VARCHAR(255),
    url VARCHAR(1000),
    jurisdiction VARCHAR(100) DEFAULT 'Chile',
    matter_area VARCHAR(100),
    license_info TEXT,
    reliability_level VARCHAR(50) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_legal_sources_type ON legal_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_legal_sources_matter_area ON legal_sources(matter_area);
CREATE INDEX IF NOT EXISTS idx_legal_sources_status ON legal_sources(status);

-- Legal source versions
CREATE TABLE IF NOT EXISTS legal_source_versions (
    id SERIAL PRIMARY KEY,
    legal_source_id INTEGER NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE,
    version_label VARCHAR(100),
    content TEXT NOT NULL,
    content_hash VARCHAR(255),
    published_at TIMESTAMP,
    consulted_at TIMESTAMP,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_legal_source_versions_source ON legal_source_versions(legal_source_id);
CREATE INDEX IF NOT EXISTS idx_legal_source_versions_current ON legal_source_versions(is_current);
