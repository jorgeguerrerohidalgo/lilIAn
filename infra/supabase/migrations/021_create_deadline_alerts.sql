-- Migration: Create deadline_alerts table
-- Purpose: Store automatic deadline alerts extracted from contract_timeline

CREATE TABLE IF NOT EXISTS deadline_alerts (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id) NOT NULL,
    matter_id INTEGER REFERENCES matters(id) NOT NULL,
    document_id INTEGER REFERENCES documents(id),
    user_id INTEGER REFERENCES users(id),

    -- Alert identification
    title VARCHAR(500) NOT NULL,
    description TEXT,
    event_type VARCHAR(50) NOT NULL,

    -- Dates
    due_date DATE NOT NULL,
    days_remaining INTEGER,
    is_overdue BOOLEAN DEFAULT FALSE,

    -- Urgency
    urgency VARCHAR(20) NOT NULL,
    importance_score INTEGER DEFAULT 50,

    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    acknowledged_by INTEGER REFERENCES users(id),
    resolved_by INTEGER REFERENCES users(id),

    -- Source from contract_timeline
    source_event VARCHAR(255),
    legal_reference VARCHAR(500),
    consequence TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_deadline_alerts_org ON deadline_alerts(organization_id);
CREATE INDEX idx_deadline_alerts_matter ON deadline_alerts(matter_id);
CREATE INDEX idx_deadline_alerts_document ON deadline_alerts(document_id);
CREATE INDEX idx_deadline_alerts_due_date ON deadline_alerts(due_date);
CREATE INDEX idx_deadline_alerts_status ON deadline_alerts(status);
CREATE INDEX idx_deadline_alerts_urgency ON deadline_alerts(urgency);

-- RLS Policies
ALTER TABLE deadline_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their organization's alerts"
    ON deadline_alerts FOR SELECT
    USING (organization_id IN (
        SELECT o.id FROM organizations o
        JOIN user_organizations uo ON o.id = uo.organization_id
        WHERE uo.user_id = auth.uid()
    ));

CREATE POLICY "Users can update alerts in their organization"
    ON deadline_alerts FOR UPDATE
    USING (organization_id IN (
        SELECT o.id FROM organizations o
        JOIN user_organizations uo ON o.id = uo.organization_id
        WHERE uo.user_id = auth.uid()
    ));
