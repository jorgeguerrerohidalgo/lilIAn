-- Analysis reports table
CREATE TABLE IF NOT EXISTS analysis_reports (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    generated_by_user_id INTEGER REFERENCES users(id),
    model_provider VARCHAR(100),
    model_name VARCHAR(100),
    report_type VARCHAR(100) DEFAULT 'preliminary_case_analysis',
    summary TEXT,
    facts TEXT,
    missing_information TEXT,
    next_steps TEXT,
    disclaimer TEXT,
    confidence VARCHAR(50) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'generated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_matter ON analysis_reports(matter_id);
CREATE INDEX IF NOT EXISTS idx_analysis_reports_organization ON analysis_reports(organization_id);
CREATE INDEX IF NOT EXISTS idx_analysis_reports_status ON analysis_reports(status);
