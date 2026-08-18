-- Step three of three, and it must NOT run with the others.
--
-- Run this only once code WITHOUT created_by on these two models is fully
-- deployed. SQLAlchemy selects every mapped column, so dropping it while any
-- container still maps it fails every query against these tables — which during a
-- blue-green switch means the previous container, still serving.
--
--   step 1  26-08-18--add_ai_generator_to_audio_lessons.sql       (deployed)
--   step 2  26-08-18-b--created_by_nullable_on_audio_lesson_scripts.sql (deployed)
--   step 3  this file, AFTER the deploy that removes it from the models
--
-- Nothing is lost. Every row holds the literal 'claude-v1' — including the scripts
-- DeepSeek wrote while the Anthropic spend cap was reached, which is exactly why
-- it could never answer "which model wrote this". ai_generator_id answers it now.
--
-- daily_audio_lesson and daily_audio_lesson_wrapper keep their created_by: those
-- record which pipeline built a row, not which model wrote a script, and nothing
-- supersedes them.

ALTER TABLE audio_lesson_meaning  DROP COLUMN created_by;
ALTER TABLE audio_lesson_dialogue DROP COLUMN created_by;
