-- (meaning, level) pairs the nightly prefetch fell short on: the LLM's
-- examples could not be anchored or were rejected. They pause (a week, a
-- month, then for good until the example prompt changes) instead of going to
-- the LLM every night. A new table, so nothing existing is rebuilt.
CREATE TABLE example_generation_attempt (
    id INT(11) NOT NULL AUTO_INCREMENT,
    meaning_id INT(11) NOT NULL,
    cefr_level VARCHAR(2) NOT NULL,
    prompt_version VARCHAR(32) NOT NULL,
    short_tries INT(11) NOT NULL DEFAULT 0,
    last_try_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY meaning_id (meaning_id, cefr_level),
    CONSTRAINT example_generation_attempt_ibfk_1 FOREIGN KEY (meaning_id)
        REFERENCES meaning (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
