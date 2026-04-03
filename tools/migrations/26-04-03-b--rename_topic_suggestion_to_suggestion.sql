ALTER TABLE daily_audio_lesson
CHANGE COLUMN topic_suggestion suggestion VARCHAR(100) DEFAULT NULL;

ALTER TABLE audio_lesson_meaning
CHANGE COLUMN topic_suggestion suggestion VARCHAR(100) DEFAULT NULL;
