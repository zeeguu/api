-- created_by on the two audio-lesson script tables is superseded by
-- ai_generator_id (26-08-18--add_ai_generator_to_audio_lessons.sql), which names
-- the model that actually answered and the prompt version behind it.
--
-- Step two of three. The code deployed with this migration stops writing the
-- column; existing rows keep their value, which is the literal 'claude-v1' on
-- every one of them — including the scripts DeepSeek wrote while the Anthropic
-- spend cap was reached. It can only be DROPped in a later deploy, once nothing
-- running still selects it: SQLAlchemy selects every mapped column, so removing
-- it while the previous container is still serving would fail every query
-- against these tables mid blue-green switch.

ALTER TABLE audio_lesson_meaning  MODIFY created_by VARCHAR(255) NULL;
ALTER TABLE audio_lesson_dialogue MODIFY created_by VARCHAR(255) NULL;
