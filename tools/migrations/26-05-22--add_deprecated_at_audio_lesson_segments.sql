-- Add a deprecation flag to cached audio lesson scripts so we can stop
-- recycling specific scripts into newly generated daily audio lessons
-- (e.g. ones produced under an earlier, ambiguous prompt template).
--
-- Forward-only gate: existing daily_audio_lesson_segment rows that reference
-- a deprecated audio_lesson_meaning / audio_lesson_dialogue keep playing as
-- before. Only future lookups via .find() / .find_unheard() skip them and
-- fall through to fresh generation.

ALTER TABLE audio_lesson_meaning
    ADD COLUMN deprecated_at TIMESTAMP NULL DEFAULT NULL
        COMMENT 'When set, lookup helpers skip this row and force regeneration.';

ALTER TABLE audio_lesson_dialogue
    ADD COLUMN deprecated_at TIMESTAMP NULL DEFAULT NULL
        COMMENT 'When set, lookup helpers skip this row and force regeneration.';
