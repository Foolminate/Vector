ALTER TABLE jobs ADD COLUMN seek_job_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_seek_job_id ON jobs(seek_job_id);
