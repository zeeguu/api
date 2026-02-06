-- Add teacher_language_id column to audio_lesson_meaning table
-- This enables caching audio lessons per (meaning, teacher_language) pair
-- so that users with different native languages get different teacher voices

ALTER TABLE audio_lesson_meaning
ADD COLUMN teacher_language_id INT DEFAULT NULL,
ADD CONSTRAINT fk_audio_lesson_meaning_teacher_language
    FOREIGN KEY (teacher_language_id) REFERENCES language(id);
