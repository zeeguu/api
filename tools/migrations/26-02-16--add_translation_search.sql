-- Translation search history table
-- Tracks searches made in the Translation Tab for history view
CREATE TABLE translation_search (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    search_word VARCHAR(255) NOT NULL,
    search_word_language_id INT NOT NULL,
    target_language_id INT NOT NULL,
    meaning_id INT NULL,
    search_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (search_word_language_id) REFERENCES language(id),
    FOREIGN KEY (target_language_id) REFERENCES language(id),
    FOREIGN KEY (meaning_id) REFERENCES meaning(id),

    INDEX idx_user_time (user_id, search_time DESC)
);
