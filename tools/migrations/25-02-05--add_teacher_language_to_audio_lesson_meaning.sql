-- Add teacher_language column to audio_lesson_meaning table
-- This enables caching audio lessons per (meaning, teacher_language) pair
-- so that users with different native languages get different teacher voices

ALTER TABLE audio_lesson_meaning
ADD COLUMN teacher_language VARCHAR(10) DEFAULT NULL
COMMENT 'Language code for the teacher voice (e.g., en, uk, da)';
