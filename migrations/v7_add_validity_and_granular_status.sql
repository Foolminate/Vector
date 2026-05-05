-- Add validity columns and support for more granular statuses
ALTER TABLE jobs ADD COLUMN last_checked_at TIMESTAMP;
ALTER TABLE jobs ADD COLUMN is_valid INTEGER DEFAULT 1; -- 1 for true, 0 for false
ALTER TABLE jobs ADD COLUMN last_decision_by TEXT DEFAULT 'robot'; -- 'robot' or 'human'
ALTER TABLE jobs ADD COLUMN expiration_date TIMESTAMP;
