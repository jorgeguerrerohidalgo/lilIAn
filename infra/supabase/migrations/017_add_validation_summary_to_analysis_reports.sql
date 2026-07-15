-- Add validation_summary column to analysis_reports
ALTER TABLE analysis_reports
ADD COLUMN IF NOT EXISTS validation_summary TEXT;

-- Comment for documentation
COMMENT ON COLUMN analysis_reports.validation_summary IS 'JSON summary of document validation results including missing documents and inconsistencies';
