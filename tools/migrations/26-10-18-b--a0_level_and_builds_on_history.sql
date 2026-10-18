-- Level A0: for learners who have never studied the language.
--
-- user_language.cefr_level is 1..6 for A1..C2. 0 was the constructor default,
-- so it has meant "not set" (6007 rows on 2026-10-18, almost all for languages
-- the user is not learning) -- and User.cefr_level_for_language indexed it as
-- [0 - 1], which made an unset level read as C2. "Not set" becomes NULL, and 0
-- from now on means A0.
UPDATE user_language SET cefr_level = NULL WHERE cefr_level = 0;

ALTER TABLE audio_lesson_dialogue
    MODIFY COLUMN difficulty_level ENUM('A0', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2') NULL;

ALTER TABLE audio_lesson_meaning
    MODIFY COLUMN difficulty_level ENUM('A0', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2') NULL;

-- builds_on_history: the script was written from the words this learner heard
-- in earlier audio lessons, so it belongs to them alone and is never reused for
-- anyone else (such a row is always is_general = 0).
ALTER TABLE audio_lesson_dialogue
    ADD COLUMN builds_on_history TINYINT(1) NOT NULL DEFAULT 0;
