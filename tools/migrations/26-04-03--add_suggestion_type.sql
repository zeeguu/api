ALTER TABLE daily_audio_lesson
ADD COLUMN suggestion_type VARCHAR(20) DEFAULT NULL
AFTER topic_suggestion;

ALTER TABLE audio_lesson_meaning
ADD COLUMN suggestion_type VARCHAR(20) DEFAULT NULL
AFTER topic_suggestion;
