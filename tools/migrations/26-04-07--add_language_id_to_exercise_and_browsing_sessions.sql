-- Capture the user's learned_language_id at the moment an exercise or
-- browsing session is created, so streak attribution doesn't depend on
-- the user's *current* learned_language at update time. Without this,
-- a tail update for a session started in language A that arrives after
-- the user toggles to language B would credit B's streak. Listening,
-- reading, and watching sessions don't need this column because they
-- can derive language from their content (daily_audio_lesson, article,
-- video). See activity_sessions._session_language.
--
-- Nullable so existing rows backfill as NULL; the helper falls back to
-- user.learned_language for old rows.

ALTER TABLE user_exercise_session ADD COLUMN language_id INT DEFAULT NULL;
ALTER TABLE user_browsing_session ADD COLUMN language_id INT DEFAULT NULL;
