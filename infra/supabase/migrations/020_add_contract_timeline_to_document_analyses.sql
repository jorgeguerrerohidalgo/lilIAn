-- Add contract_timeline column for timeline extraction
ALTER TABLE document_analyses ADD COLUMN IF NOT EXISTS contract_timeline JSONB DEFAULT '[]'::jsonb;
