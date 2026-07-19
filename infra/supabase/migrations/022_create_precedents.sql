-- Migration: Create precedents table for judicial precedents search
-- Date: 2026-07-17

CREATE TABLE IF NOT EXISTS precedents (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,

    -- Identificacion unica de la sentencia
    court VARCHAR(200) NOT NULL,
    tribunal VARCHAR(200) NOT NULL,
    year INTEGER NOT NULL,
    roll_number VARCHAR(50) NOT NULL,
    full_citation VARCHAR(500),

    -- Clasificacion
    legal_area VARCHAR(50) NOT NULL DEFAULT 'other',
    matter_type VARCHAR(100),

    -- Contenido
    summary TEXT NOT NULL,
    reasoning TEXT,
    decision TEXT,
    disposition TEXT,
    voces VARCHAR(500),

    -- Metadata adicional
    ponente VARCHAR(200),
    type VARCHAR(50),
    precedent_metadata TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(organization_id, court, year, roll_number)
);

-- Indices para busqueda eficiente
CREATE INDEX idx_precedents_court ON precedents(court);
CREATE INDEX idx_precedents_year ON precedents(year);
CREATE INDEX idx_precedents_legal_area ON precedents(legal_area);
CREATE INDEX idx_precedents_matter_type ON precedents(matter_type);
CREATE INDEX idx_precedents_organization ON precedents(organization_id);
CREATE INDEX idx_precedents_court_year ON precedents(court, year);
CREATE INDEX idx_precedents_summary_trgm ON precedents USING gin(summary gin_trgm_ops);

-- Comentarios
COMMENT ON TABLE precedents IS 'Sentencias judiciales chilenas para busqueda de precedentes';
COMMENT ON COLUMN precedents.court IS 'Tribunal que emitió la sentencia (ej: Corte Suprema)';
COMMENT ON COLUMN precedents.tribunal IS 'Juzgado o tribunal especifico';
COMMENT ON COLUMN precedents.year IS 'Año de la sentencia';
COMMENT ON COLUMN precedents.roll_number IS 'Número de rol de la causa';
COMMENT ON COLUMN precedents.full_citation IS 'Cita completa (ej: CS, 15.01.2020, Rol 1234-2019)';
COMMENT ON COLUMN precedents.legal_area IS 'Área legal (laboral, civil, penal, etc.)';
COMMENT ON COLUMN precedents.matter_type IS 'Tipo de materia o tipo de juicio';
COMMENT ON COLUMN precedents.summary IS 'Resumen ejecutivo de la sentencia';
COMMENT ON COLUMN precedents.reasoning IS 'Considerandos o razonamiento del tribunal';
COMMENT ON COLUMN precedents.decision IS 'Fallo o parte resolutiva';
COMMENT ON COLUMN precedents.disposition IS 'Parte dispositiva completa';
COMMENT ON COLUMN precedents.voces IS 'Materias juridicas (Separatas/Voces)';
COMMENT ON COLUMN precedents.ponente IS 'Ministro redactor';
COMMENT ON COLUMN precedents.precedent_metadata IS 'JSON con embedding y metadata de indexacion';

-- RLS Policies
ALTER TABLE precedents ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view precedents from their organization
CREATE POLICY "users_view_own_org_precedents"
    ON precedents FOR SELECT
    USING (
        organization_id = (
            SELECT organization_id
            FROM organization_members
            WHERE user_id = auth.uid()
            LIMIT 1
        )
    );

-- Policy: Users can insert precedents in their organization
CREATE POLICY "users_insert_own_org_precedents"
    ON precedents FOR INSERT
    WITH CHECK (
        organization_id = (
            SELECT organization_id
            FROM organization_members
            WHERE user_id = auth.uid()
            LIMIT 1
        )
    );

-- Policy: Users can update precedents in their organization
CREATE POLICY "users_update_own_org_precedents"
    ON precedents FOR UPDATE
    USING (
        organization_id = (
            SELECT organization_id
            FROM organization_members
            WHERE user_id = auth.uid()
            LIMIT 1
        )
    );

-- Policy: Users can delete precedents in their organization
CREATE POLICY "users_delete_own_org_precedents"
    ON precedents FOR DELETE
    USING (
        organization_id = (
            SELECT organization_id
            FROM organization_members
            WHERE user_id = auth.uid()
            LIMIT 1
        )
    );
