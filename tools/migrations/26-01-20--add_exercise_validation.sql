-- Add validated column to meaning table
-- Tracks whether a translation has been validated before entering exercises
-- Values: 0=not validated, 1=validated as correct, 2=was wrong and has been fixed

ALTER TABLE meaning
ADD COLUMN validated TINYINT(1) NOT NULL DEFAULT 0
COMMENT 'Validation status: 0=unknown, 1=valid, 2=invalid/fixed';
