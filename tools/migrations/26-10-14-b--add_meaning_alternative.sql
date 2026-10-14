-- Other words a learner may type for a meaning in a cloze exercise, as judged
-- by an LLM once and then reused: e.g. for 'synes' (think, as in an opinion)
-- the learner types 'tænker'.
--
-- Keyed on the expected MEANING, not the expected phrase: the meaning fixes
-- the sense ('synes' = to think, have an opinion), so a verdict about it
-- carries over to other sentences. When the judge says its verdict only holds
-- in this one sentence, context_hash is the sentence's SHA-256 and only that
-- sentence reuses it. For a general verdict context_hash is '' (not NULL, so
-- the unique key holds for general verdicts too).
--
-- user_id: NULL for a verdict shared by all learners. An accepting verdict
-- (SYNONYM or NEAR_SYNONYM_NOT_IDIOMATIC) for a typed form that is not a
-- known phrase of the language is kept for the learner who typed it only, so
-- one learner's odd input cannot make an answer right for everybody.
--
-- The alternative is stored as text, not as a phrase row: most typed answers
-- are wrong, and wrong answers do not belong in the phrase table. Binary
-- collation, so 'esta' and 'está', 'pa' and 'på' are different answers.

CREATE TABLE meaning_alternative (
    id INT AUTO_INCREMENT PRIMARY KEY,
    meaning_id INT NOT NULL,
    alternative VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL
        COMMENT 'lowercased, trimmed typed answer',
    context_hash CHAR(64) NOT NULL DEFAULT ''
        COMMENT 'sentence SHA-256 if the verdict only holds there, else empty',
    user_id INT NULL
        COMMENT 'NULL: shared by all learners. Set: only for this learner',
    relation ENUM('SYNONYM', 'NEAR_SYNONYM_NOT_IDIOMATIC', 'NOT_SYNONYM') NOT NULL,
    explanation TEXT,
    ai_generator_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_meaning_alternative (meaning_id, alternative, context_hash, user_id),
    FOREIGN KEY (meaning_id) REFERENCES meaning(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (ai_generator_id) REFERENCES ai_generator(id) ON DELETE SET NULL
) DEFAULT CHARSET=utf8mb4;
