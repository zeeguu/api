-- Engagement (is_engaged / waiting_paused_for) must measure the FURTHEST
-- position the learner reached, not the resume pointer (pause_position_seconds),
-- which drops when they rewind/scrub back. Add a monotonic high-water-mark.
--
-- Backfill existing rows from pause_position_seconds (our best estimate of how
-- far they got) so the engagement gate doesn't regress for current lessons.
ALTER TABLE daily_audio_lesson
ADD COLUMN max_position_seconds INT NOT NULL DEFAULT 0
COMMENT 'Furthest playback position ever reached (monotonic); drives engagement, unlike the rewind-able pause_position_seconds';

-- Backfill: the column is brand new (so it's 0 everywhere) — seed it from the
-- best estimate of how far each learner got.
UPDATE daily_audio_lesson
SET max_position_seconds = GREATEST(
  COALESCE(pause_position_seconds, 0),
  -- A completed lesson was heard in full; credit its whole duration.
  CASE WHEN last_completed_at IS NOT NULL THEN COALESCE(duration_seconds, 0) ELSE 0 END
);
