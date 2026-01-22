-- Add literal_meaning column for idioms
-- Shows word-by-word translation to help learners understand idiom origins

ALTER TABLE meaning
ADD COLUMN literal_meaning TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
COMMENT 'Word-by-word literal translation for idioms (e.g., "kick into touch" for "botter en touche")';
