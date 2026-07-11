-- Matters table
CREATE TABLE IF NOT EXISTS matters (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    assigned_lawyer_id INTEGER REFERENCES users(id),
    title VARCHAR(500) NOT NULL,
    matter_type VARCHAR(50) DEFAULT 'other',
    description TEXT,
    status VARCHAR(50) DEFAULT 'new',
    urgency VARCHAR(50) DEFAULT 'medium',
    counterparty_name VARCHAR(255),
    relevant_date TIMESTAMP,
    source_channel VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_matters_organization ON matters(organization_id);
CREATE INDEX IF NOT EXISTS idx_matters_status ON matters(status);
CREATE INDEX IF NOT EXISTS idx_matters_matter_type ON matters(matter_type);
CREATE INDEX IF NOT EXISTS idx_matters_created_by ON matters(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_matters_created_at ON matters(created_at DESC);
