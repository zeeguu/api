ALTER TABLE audio_lesson_meaning
    DROP COLUMN suggestion,
    DROP COLUMN suggestion_type,
    DROP COLUMN lesson_type;

ALTER TABLE daily_audio_lesson
    CHANGE COLUMN suggestion canonical_suggestion VARCHAR(100) DEFAULT NULL;
