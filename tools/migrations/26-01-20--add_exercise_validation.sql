-- Add exercise_validated column to meaning table
-- This tracks whether a translation has been validated by LLM before entering exercises
-- Values: 0=not validated, 1=validated as correct, 2=was wrong and has been fixed

ALTER TABLE meaning
ADD COLUMN exercise_validated TINYINT(1) NOT NULL DEFAULT 0
COMMENT 'LLM validation status: 0=unknown, 1=valid, 2=invalid/fixed';
