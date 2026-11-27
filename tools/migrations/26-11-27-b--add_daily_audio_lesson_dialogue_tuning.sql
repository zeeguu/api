-- The pace and repetition a lesson above A0 says its shared dialogue with,
-- when the learner tuned them (lesson_tuning.LessonTuning as JSON); the lesson
-- then has its own copy of the dialogue's audio. NULL: the shared audio.
ALTER TABLE daily_audio_lesson ADD COLUMN dialogue_tuning JSON NULL;
