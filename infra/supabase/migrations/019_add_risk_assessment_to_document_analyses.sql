-- Add risk_assessment column to document_analyses table
ALTER TABLE document_analyses ADD COLUMN IF NOT EXISTS risk_assessment JSONB DEFAULT '[]'::jsonb;
