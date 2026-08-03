-- Migration: 026_create_reviews
-- Description: Crear tabla reviews para workflow de revisión de análisis
-- Date: 2026-08-01

-- Tabla de reviews para workflow: draft → pending → approved/rejected
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    analysis_report_id INTEGER NOT NULL REFERENCES analysis_reports(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    reviewed_by_user_id INTEGER REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    comments TEXT,
    rejection_reason TEXT,
    suggested_changes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP WITH TIME ZONE
);

-- Índices para queries comunes
CREATE INDEX IF NOT EXISTS idx_reviews_analysis_report_id ON reviews(analysis_report_id);
CREATE INDEX IF NOT EXISTS idx_reviews_organization_id ON reviews(organization_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);
CREATE INDEX IF NOT EXISTS idx_reviews_created_by_user_id ON reviews(created_by_user_id);

-- Constraints de status
ALTER TABLE reviews ADD CONSTRAINT chk_reviews_status
    CHECK (status IN ('draft', 'pending', 'approved', 'rejected'));

-- Verificar creación
-- SELECT * FROM reviews LIMIT 1;
