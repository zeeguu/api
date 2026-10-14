-- Other words a learner may type for a meaning in a cloze exercise, as judged
-- by an LLM once and then shared by all learners: e.g. for 'synes' (think,
-- as in an opinion) the learner types 'tænker'.
--
-- Keyed on the expected MEANING, not the expected phrase: the meaning fixes
-- the sense ('synes' = to think, have an opinion), so a verdict about it
-- carries over to other sentences. When the judge says its verdict only holds
-- in this one sentence, context_hash is the sentence's SHA-256 and only that
-- sentence reuses it, and for a general verdict context_hash is ''. ('' rather
-- than NULL so the unique key also holds for general verdicts.)
--
-- The alternative is stored as text, not as a phrase row: most typed answers
-- are wrong, and wrong answers do not belong in the phrase table.

CREATE TABLE meaning_alternative (
    id INT AUTO_INCREMENT PRIMARY KEY,
    meaning_id INT NOT NULL,
    alternative VARCHAR(255) NOT NULL COMMENT 'lowercased, trimmed typed answer',
    context_hash CHAR(64) NOT NULL DEFAULT '' COMMENT 'sentence SHA-256 if the verdict only holds there, else empty',
    relation ENUM('SYNONYM', 'NEAR_SYNONYM_NOT_IDIOMATIC', 'NOT_SYNONYM') NOT NULL,
    explanation TEXT,
    ai_generator_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_meaning_alternative (meaning_id, alternative, context_hash),
    FOREIGN KEY (meaning_id) REFERENCES meaning(id) ON DELETE CASCADE,
    FOREIGN KEY (ai_generator_id) REFERENCES ai_generator(id) ON DELETE SET NULL
);
