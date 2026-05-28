-- New lessons mint share_uuid at creation time (DailyAudioLesson.__init__).
-- Backfill the existing rows that were created before that, so the client can
-- always build a share link without a round-trip. MySQL UUID() yields a fresh
-- 36-char value per row, matching the share_uuid column.
UPDATE daily_audio_lesson
SET share_uuid = UUID()
WHERE share_uuid IS NULL;
