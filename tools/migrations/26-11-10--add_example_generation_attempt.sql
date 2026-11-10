-- How often the nightly prefetch wrote examples for a (meaning, level) since
-- it last had enough. A meaning short again after a try (examples not
-- anchorable, or rejected by the validator later) pauses: a week, a month,
-- then for good until the generator (LLM model or prompt) changes, instead
-- of going to the LLM every night. A new table, so nothing existing is rebuilt.
CREATE TABLE example_generation_attempt (
    id INT(11) NOT NULL AUTO_INCREMENT,
    meaning_id INT(11) NOT NULL,
    cefr_level VARCHAR(2) NOT NULL,
    ai_generator_id INT(11) NOT NULL,
    tries INT(11) NOT NULL DEFAULT 0,
    last_try_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY meaning_id (meaning_id, cefr_level),
    CONSTRAINT example_generation_attempt_ibfk_1 FOREIGN KEY (meaning_id)
        REFERENCES meaning (id) ON DELETE CASCADE,
    CONSTRAINT example_generation_attempt_ibfk_2 FOREIGN KEY (ai_generator_id)
        REFERENCES ai_generator (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
