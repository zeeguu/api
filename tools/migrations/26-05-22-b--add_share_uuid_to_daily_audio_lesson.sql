ALTER TABLE daily_audio_lesson
ADD COLUMN share_uuid VARCHAR(36) DEFAULT NULL,
ADD UNIQUE INDEX idx_daily_audio_lesson_share_uuid (share_uuid);
