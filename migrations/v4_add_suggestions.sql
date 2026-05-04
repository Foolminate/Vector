-- Migration: Add search_suggestions table for AI-driven discovery
CREATE TABLE IF NOT EXISTS search_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keywords TEXT NOT NULL,
    source_keyword TEXT,
    total_jobs INTEGER,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    UNIQUE(keywords)
);
