-- Rename DailyAudioLesson.completed_at to last_completed_at.
-- Completion is sticky (a historical fact); replaying a completed lesson
-- no longer clears it. Naming makes that explicit: this is the timestamp
-- of the most recent completion, never reset to NULL once set.

ALTER TABLE daily_audio_lesson
  CHANGE COLUMN completed_at last_completed_at TIMESTAMP NULL;
