-- Add generated column for lowercase content and index for fast case-insensitive lookups
-- This fixes the slow Meaning.find_or_create query (was 2-3.5s, should be <50ms)

-- Add generated column that stores lowercase version of content
ALTER TABLE phrase
ADD COLUMN content_lower VARCHAR(255)
GENERATED ALWAYS AS (LOWER(content)) STORED;

-- Create composite index for fast lookups by language + lowercase content
CREATE INDEX idx_phrase_lang_content_lower ON phrase(language_id, content_lower);
