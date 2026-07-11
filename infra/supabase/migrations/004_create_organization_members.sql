-- Organization members table
CREATE TABLE IF NOT EXISTS organization_members (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'client',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_organization_members_organization ON organization_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_organization_members_user ON organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_organization_members_role ON organization_members(role);
