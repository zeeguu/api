-- The validator can give up on a meaning in a sentence (BROKEN_SENTENCE,
-- WORD_NOT_FIT). That is not "invalid": the meaning is left as it is, only
-- this learner's word leaves study. Appending a value at the end of the enum
-- is a metadata-only change; the table is small anyway (~22k rows).
ALTER TABLE validation_log
    MODIFY COLUMN action ENUM('valid', 'fixed', 'invalid', 'gave_up')
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL;
