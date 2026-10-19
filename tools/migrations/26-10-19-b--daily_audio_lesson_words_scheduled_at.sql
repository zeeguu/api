-- A0 lessons put the words they taught on the learner's study list after the
-- lesson is completed (zeeguu/api#867). words_scheduled_at records that it was
-- done: two "complete" requests at once no longer both run it, and a run that
-- failed (the model call failed, or its answer could not be read) is tried
-- again the next time the learner completes an A0 lesson.
--
-- Lessons completed before this count as done: those after #867 were
-- scheduled, and the ones before had no such step.
ALTER TABLE daily_audio_lesson
    ADD COLUMN words_scheduled_at DATETIME NULL DEFAULT NULL;

UPDATE daily_audio_lesson
    SET words_scheduled_at = last_completed_at
    WHERE last_completed_at IS NOT NULL;
