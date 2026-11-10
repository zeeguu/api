-- Curated word lists (an exam list like PD3, later basic vocabulary, teacher
-- lists), meant to be highlighted in what learners read. Entries are plain
-- text as the list's author wrote them. New tables, so nothing is rebuilt.
CREATE TABLE word_list (
    id INT(11) NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    language_id INT(11) NOT NULL,
    translation_language_id INT(11) DEFAULT NULL,
    origin TEXT,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY name (name, language_id),
    CONSTRAINT word_list_ibfk_1 FOREIGN KEY (language_id) REFERENCES language (id),
    CONSTRAINT word_list_ibfk_2 FOREIGN KEY (translation_language_id) REFERENCES language (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE word_list_entry (
    id INT(11) NOT NULL AUTO_INCREMENT,
    word_list_id INT(11) NOT NULL,
    position INT(11) NOT NULL,
    section VARCHAR(255) DEFAULT NULL,
    phrase VARCHAR(255) NOT NULL,
    translation VARCHAR(255) DEFAULT NULL,
    example TEXT,
    PRIMARY KEY (id),
    UNIQUE KEY word_list_id (word_list_id, phrase),
    CONSTRAINT word_list_entry_ibfk_1 FOREIGN KEY (word_list_id)
        REFERENCES word_list (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
