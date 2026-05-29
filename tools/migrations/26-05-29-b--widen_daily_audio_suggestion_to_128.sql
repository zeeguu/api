-- Align the daily-audio suggestion length to 128 across the board (was 100 on
-- the lesson, 255 on the new subscription). 128 is the single cap enforced at
-- the API/mirror input, so widen the lesson columns to match and avoid
-- truncation when a long subject flows from the subscription into generation.
ALTER TABLE daily_audio_lesson
  MODIFY COLUMN raw_suggestion VARCHAR(128) DEFAULT NULL,
  MODIFY COLUMN canonical_suggestion VARCHAR(128) DEFAULT NULL;
