-- Risk items table
CREATE TABLE IF NOT EXISTS risk_items (
    id SERIAL PRIMARY KEY,
    analysis_report_id INTEGER REFERENCES analysis_reports(id) ON DELETE CASCADE,
    matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    level VARCHAR(20) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    source_fragment TEXT,
    impact TEXT,
    recommendation TEXT,
    confidence VARCHAR(50) DEFAULT 'medium',
    review_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_items_report ON risk_items(analysis_report_id);
CREATE INDEX IF NOT EXISTS idx_risk_items_matter ON risk_items(matter_id);
CREATE INDEX IF NOT EXISTS idx_risk_items_level ON risk_items(level);
CREATE INDEX IF NOT EXISTS idx_risk_items_review_status ON risk_items(review_status);
