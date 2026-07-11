-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) DEFAULT 'individual',
    rut VARCHAR(50),
    billing_email VARCHAR(255),
    plan_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_organizations_type ON organizations(type);
CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);
