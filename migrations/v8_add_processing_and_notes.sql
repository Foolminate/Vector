-- Migration: v8_add_processing_and_notes.sql
-- Add processing status for background tasks and ensure notes exists

-- Add processing_status if it doesn't exist (using a safe way for SQLite)
-- Since SQLite doesn't have 'IF NOT EXISTS' for columns, we just attempt it or check table info.
-- But the migration runner should ideally handle this.
ALTER TABLE jobs ADD COLUMN processing_status TEXT DEFAULT 'idle';

-- Ensure notes exists (it was added in v5, but we can verify or just let it be)
-- If we want to be idempotent and safe, we can't easily do IF NOT EXISTS in ALTER TABLE in SQLite.
-- Given it's a migration runner, we assume migrations run sequentially.
