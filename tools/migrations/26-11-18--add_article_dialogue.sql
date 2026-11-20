-- A short dialogue for absolute beginners (A0), written from an article and
-- read in the reader as its own text, "inspired by" that article.
--
-- The dialogue is an article row of its own, so the reader's translation,
-- bookmarks and exercises work on it unchanged. It is linked to the article it
-- comes from only here, not through article.parent_article_id: everything that
-- follows parent_article_id treats the child as a simplification (level
-- switcher, on-demand simplification, pruning, indexing).
--
-- The dialogue article has one fragment per spoken line. speakers names who
-- says each fragment, in order, so the names never become words of the text
-- (tokens, bookmark contexts, text-to-speech).
--
-- Deleting the dialogue article deletes this row. The inspiring article cannot
-- be deleted while a dialogue points at it (pruning skips it: see
-- PROTECTING_COLUMNS in zeeguu/core/article_pruning.py).

CREATE TABLE article_dialogue (
    article_id INT NOT NULL,
    inspired_by_article_id INT NOT NULL,
    speakers JSON NOT NULL,
    writer_ai_generator_id INT NULL,
    checker_ai_generator_id INT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (article_id),
    KEY ix_article_dialogue_inspired_by (inspired_by_article_id),
    CONSTRAINT fk_article_dialogue_article FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE CASCADE,
    CONSTRAINT fk_article_dialogue_inspired_by FOREIGN KEY (inspired_by_article_id) REFERENCES article (id) ON DELETE RESTRICT,
    CONSTRAINT fk_article_dialogue_writer FOREIGN KEY (writer_ai_generator_id) REFERENCES ai_generator (id),
    CONSTRAINT fk_article_dialogue_checker FOREIGN KEY (checker_ai_generator_id) REFERENCES ai_generator (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
