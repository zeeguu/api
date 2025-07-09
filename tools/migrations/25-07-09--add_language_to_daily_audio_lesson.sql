-- Add language tracking to daily audio lessons
-- This ensures lessons are filtered by the user's currently learned language

-- Add language_id column to daily_audio_lesson table
ALTER TABLE daily_audio_lesson
ADD COLUMN language_id INT
DEFAULT NULL
COMMENT 'The learned language for this lesson';

-- Add foreign key constraint
ALTER TABLE daily_audio_lesson
ADD CONSTRAINT fk_daily_audio_lesson_language
FOREIGN KEY (language_id) REFERENCES language (id);

-- Create index for efficient queries by user and language
CREATE INDEX idx_daily_audio_lesson_user_language 
ON daily_audio_lesson(user_id, language_id);

-- Example usage:
-- SELECT * FROM daily_audio_lesson 
-- WHERE user_id = 123 AND language_id = 5
-- ORDER BY created_at DESC;