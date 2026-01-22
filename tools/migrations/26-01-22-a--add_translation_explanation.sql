-- Add explanation column for additional translation context
-- This keeps the main translation short for exercises while allowing richer context for learning

ALTER TABLE meaning
ADD COLUMN translation_explanation TEXT DEFAULT NULL
COMMENT 'Optional explanation of translation usage, nuances, or context';
