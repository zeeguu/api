-- Which translator produced a translation, so broken pairs can be traced back
-- to the engine that made them. On 2026-10-18 a check of 200 audio lessons found
-- pairs like connu → experienced and dem → De wandeling, most of them passed by
-- our translation validator, and nothing recorded where they came from: the
-- translate endpoint returned the service to the client and dropped it.
--
-- bookmark.translation_service_id: who produced the bookmark's CURRENT
-- translation (the translate endpoint's winner, an alternative the learner
-- picked, the learner's own, the validator's fix).
--
-- validation_log.translation_service_id: who produced the translation that
-- verdict judged. A FIXED verdict moves the bookmark to the validator's pair,
-- so only the log keeps which engine got it wrong.
--
-- NULL for everything before this migration; that history is gone.
--
-- foreign_key_checks off for the ALTERs: on MySQL 5.7 adding a foreign key
-- with checks on forces ALGORITHM=COPY, which blocks writes to bookmark (every
-- lookup) while it copies; with checks off it runs INPLACE and lookups go on.
-- Safe here because the new columns are all NULL, so nothing is left unchecked.

CREATE TABLE translation_service (
    id SMALLINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL
        COMMENT 'as the translate endpoint names it, e.g. DeepL, LLM, MANUAL',
    UNIQUE KEY uq_translation_service_name (name)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET foreign_key_checks = 0;

ALTER TABLE bookmark
    ADD COLUMN translation_service_id SMALLINT NULL,
    ADD CONSTRAINT bookmark_translation_service_fk
        FOREIGN KEY (translation_service_id) REFERENCES translation_service(id);

ALTER TABLE validation_log
    ADD COLUMN translation_service_id SMALLINT NULL,
    ADD CONSTRAINT validation_log_translation_service_fk
        FOREIGN KEY (translation_service_id) REFERENCES translation_service(id);

SET foreign_key_checks = 1;
