-- Snapshot user.learned_language_id at session start so a late tail-update
-- can't be re-credited after the user switches languages. Nullable; old
-- rows fall back to user.learned_language. See activity_sessions._session_language.

ALTER TABLE user_exercise_session ADD COLUMN language_id INT DEFAULT NULL;
ALTER TABLE user_browsing_session ADD COLUMN language_id INT DEFAULT NULL;
