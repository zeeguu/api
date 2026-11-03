-- A learner's or teacher's correction of a translation, shared with everyone
-- who later looks up the same word in the same sentence (logged-in reader,
-- public article page, alternatives menu). Anchored on the sentence
-- (bookmark_context, deduplicated by its text) and the pair (meaning), not on
-- token positions, which drift with re-tokenization.
--
-- status: PENDING until the nightly validator run judges it; a teacher's is
-- ACCEPTED at once (accepted_by = TRUSTED_USER) and only audited nightly.
CREATE TABLE translation_correction (
    id INT NOT NULL AUTO_INCREMENT,
    context_id INT NOT NULL,
    meaning_id INT NOT NULL,
    bookmark_id INT NULL,
    user_id INT NULL,
    status ENUM('PENDING', 'ACCEPTED', 'REJECTED') NOT NULL DEFAULT 'PENDING',
    accepted_by ENUM('VALIDATOR', 'TRUSTED_USER') NULL,
    -- the nightly validator's verdict (VALID / FIX / BROKEN_SENTENCE / ...)
    verdict VARCHAR(32) NULL,
    reason TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    judged_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_translation_correction (context_id, meaning_id),
    KEY ix_translation_correction_meaning (meaning_id),
    KEY ix_translation_correction_status (status),
    CONSTRAINT translation_correction_context_fk FOREIGN KEY (context_id)
        REFERENCES bookmark_context (id) ON DELETE CASCADE,
    CONSTRAINT translation_correction_meaning_fk FOREIGN KEY (meaning_id)
        REFERENCES meaning (id) ON DELETE CASCADE,
    -- SET NULL, not CASCADE: the bookmark is where the correction was made,
    -- not what makes it true; it outlives a deleted word or account
    CONSTRAINT translation_correction_bookmark_fk FOREIGN KEY (bookmark_id)
        REFERENCES bookmark (id) ON DELETE SET NULL,
    CONSTRAINT translation_correction_user_fk FOREIGN KEY (user_id)
        REFERENCES user (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
