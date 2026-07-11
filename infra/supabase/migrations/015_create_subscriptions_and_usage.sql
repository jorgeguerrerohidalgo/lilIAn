-- Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    plan_name VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    documents_limit INTEGER DEFAULT 100,
    analyses_limit INTEGER DEFAULT 50,
    users_limit INTEGER DEFAULT 5,
    monthly_price INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    renews_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_organization ON subscriptions(organization_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);

-- Usage events table
CREATE TABLE IF NOT EXISTS usage_events (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id),
    event_type VARCHAR(100) NOT NULL,
    quantity INTEGER DEFAULT 1,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usage_events_organization ON usage_events(organization_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_type ON usage_events(event_type);
CREATE INDEX IF NOT EXISTS idx_usage_events_created_at ON usage_events(created_at);

-- Plans reference table
CREATE TABLE IF NOT EXISTS plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    documents_limit INTEGER DEFAULT 100,
    analyses_limit INTEGER DEFAULT 50,
    users_limit INTEGER DEFAULT 5,
    monthly_price INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO plans (name, display_name, description, documents_limit, analyses_limit, users_limit, monthly_price)
VALUES
    ('free', 'Plan Gratuito', 'Para usuarios individuales', 10, 5, 1, 0),
    ('lawyer', 'Plan Abogado', 'Para abogados independientes', 500, 200, 3, 29990),
    ('law_firm', 'Plan Estudio', 'Para estudios jurídicos', 2000, 1000, 10, 99990),
    ('company', 'Plan Empresa', 'Para empresas', 5000, 2000, 25, 199990),
    ('enterprise', 'Plan Enterprise', 'Para grandes empresas', -1, -1, -1, 0)
ON CONFLICT (name) DO NOTHING;
