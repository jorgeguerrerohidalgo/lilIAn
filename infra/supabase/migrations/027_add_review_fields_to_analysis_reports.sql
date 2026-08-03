-- Migration: 027_add_review_fields_to_analysis_reports
-- Description: Agregar campos de revisión a analysis_reports
-- Date: 2026-08-01

-- Agregar campos para gate de revisión
ALTER TABLE analysis_reports
ADD COLUMN IF NOT EXISTS requires_human_review BOOLEAN DEFAULT FALSE;

ALTER TABLE analysis_reports
ADD COLUMN IF NOT EXISTS review_approved BOOLEAN DEFAULT FALSE;

-- Crear índices para queries
CREATE INDEX IF NOT EXISTS idx_analysis_reports_requires_human_review ON analysis_reports(requires_human_review);
CREATE INDEX IF NOT EXISTS idx_analysis_reports_review_approved ON analysis_reports(review_approved);

-- Verificar
-- SELECT id, requires_human_review, review_approved FROM analysis_reports LIMIT 5;
