-- Add topic_suggestion column to audio_lesson_meaning for per-topic script isolation
ALTER TABLE audio_lesson_meaning
ADD COLUMN topic_suggestion VARCHAR(100) DEFAULT NULL
COMMENT 'Optional user-provided topic hint that themed the LLM dialogue';

-- Add topic_suggestion column to daily_audio_lesson for display in title
ALTER TABLE daily_audio_lesson
ADD COLUMN topic_suggestion VARCHAR(100) DEFAULT NULL
COMMENT 'Optional user-provided topic hint for this lesson';
