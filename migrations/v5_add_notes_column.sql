-- Migration: v5_add_notes_column.sql
-- Add human notes column to jobs table
ALTER TABLE jobs ADD COLUMN notes TEXT;
