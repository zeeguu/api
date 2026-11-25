-- A0 lessons: the character the learner played ("man" / "woman") and the
-- dialogue the lesson was built around, as the dialogue call wrote it. Both are
-- known when the lesson is written; the next lessons rehearse earlier dialogues
-- in the learner's role (words_heard.earlier_dialogues), which before this had
-- to be inferred from the script. NULL for other dialogues, and for A0 rows
-- until tools/backfill_a0_dialogue_learner.py has filled them in.
--
-- Nullable columns at the end of a small table (~550 rows).

ALTER TABLE audio_lesson_dialogue
    ADD COLUMN learner_character VARCHAR(5) NULL,
    ADD COLUMN dialogue_script TEXT NULL;
