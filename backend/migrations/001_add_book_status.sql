-- Migration: Add book status tracking to reading_progress table
-- Date: 2024-12-28
-- Description: Adds status, status_updated_at, and manually_set columns for book status tracking

-- Note: These ALTER TABLE statements are safe to run multiple times
-- The application code should check for column existence before executing each statement

-- Add status column with check constraint
-- Only run if column doesn't exist: SELECT COUNT(*) FROM pragma_table_info('reading_progress') WHERE name='status'
ALTER TABLE reading_progress
ADD COLUMN status VARCHAR(20) DEFAULT 'new'
CHECK (status IN ('new', 'reading', 'finished'));

-- Add timestamp for when status was last updated
-- Only run if column doesn't exist: SELECT COUNT(*) FROM pragma_table_info('reading_progress') WHERE name='status_updated_at'
ALTER TABLE reading_progress
ADD COLUMN status_updated_at TIMESTAMP DEFAULT '1970-01-01 00:00:00';

-- Add flag to indicate if status was manually set by user
-- Only run if column doesn't exist: SELECT COUNT(*) FROM pragma_table_info('reading_progress') WHERE name='manually_set'
ALTER TABLE reading_progress
ADD COLUMN manually_set BOOLEAN DEFAULT FALSE;

-- Update existing records to set proper timestamps (safe to run multiple times)
UPDATE reading_progress
SET status_updated_at = last_updated
WHERE status_updated_at = '1970-01-01 00:00:00';

-- Add indexes (these use IF NOT EXISTS so they're already idempotent)
CREATE INDEX IF NOT EXISTS idx_reading_progress_status ON reading_progress(status);
CREATE INDEX IF NOT EXISTS idx_reading_progress_status_updated ON reading_progress(status, status_updated_at);
