-- prompt_version at VARCHAR(50) is a tripwire: a value that does not fit raises
-- DataError from inside AIGenerator.find_or_create's bare except:, so the caller
-- sees the generation fail rather than the provenance. The audio-lesson prompt
-- filename (62 chars) hit it; the next long value would hit it the same way.
--
-- 255 matches created_by on the neighbouring tables. It costs one byte per row —
-- utf8mb4 puts the length prefix at 2 bytes above 63 characters — on a table
-- that holds one row per (model, prompt) combination. There is no index on the
-- column, so nothing else changes.
--
-- What is STORED stays short on purpose: the family and the version
-- ('meaning_lesson-v4'), not the whole filename, so rewording a prompt's
-- description does not look like a new version. This is headroom, not licence.

ALTER TABLE ai_generator MODIFY prompt_version VARCHAR(255) DEFAULT NULL;
