-- Migration: v9_refactor_cost_log.sql
-- Modernize cost_log for high-fidelity token and cost tracking

ALTER TABLE cost_log ADD COLUMN tokens_in INTEGER;
ALTER TABLE cost_log ADD COLUMN tokens_out INTEGER;
ALTER TABLE cost_log ADD COLUMN cost REAL;
ALTER TABLE cost_log ADD COLUMN task TEXT;
