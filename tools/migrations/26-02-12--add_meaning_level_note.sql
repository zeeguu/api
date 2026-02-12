-- Add level_note to meaning for caching LLM-generated CEFR assessment
ALTER TABLE meaning
ADD COLUMN level_note TEXT DEFAULT NULL
COMMENT 'Cached CEFR level assessment from LLM (e.g., "appropriate for B1")';
