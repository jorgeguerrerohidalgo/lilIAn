-- Templates table
CREATE TABLE IF NOT EXISTS templates (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
    template_type VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    content TEXT NOT NULL,
    is_global BOOLEAN DEFAULT FALSE,
    created_by_user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_templates_type ON templates(template_type);
CREATE INDEX IF NOT EXISTS idx_templates_organization ON templates(organization_id);

-- Matter notes table
CREATE TABLE IF NOT EXISTS matter_notes (
    id SERIAL PRIMARY KEY,
    matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_matter_notes_matter ON matter_notes(matter_id);
CREATE INDEX IF NOT EXISTS idx_matter_notes_user ON matter_notes(user_id);

-- Matter status history
CREATE TABLE IF NOT EXISTS matter_status_history (
    id SERIAL PRIMARY KEY,
    matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    changed_by_user_id INTEGER REFERENCES users(id),
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_matter_status_history_matter ON matter_status_history(matter_id);
