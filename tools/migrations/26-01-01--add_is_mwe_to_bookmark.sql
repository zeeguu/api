-- Add is_mwe column to bookmark table to track multi-word expressions
ALTER TABLE bookmark ADD COLUMN is_mwe BOOLEAN DEFAULT FALSE;
