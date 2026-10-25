-- Generated examples the translation validator would not pass the card in.
-- The card stays as it is; the example is not used as a context again.
-- A new table, so nothing on example_sentence is rebuilt.
CREATE TABLE example_sentence_misfit (
    example_sentence_id INT(11) NOT NULL,
    reason TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (example_sentence_id),
    CONSTRAINT example_sentence_misfit_ibfk_1 FOREIGN KEY (example_sentence_id)
        REFERENCES example_sentence (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
