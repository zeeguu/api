-- Drop old translation_search table (had meaning_id, now we just store search_word)
DROP TABLE IF EXISTS translation_search;

-- New simplified translation search history table
-- Stores the search word and learned language (active during search)
-- Filtered by current learned language when displayed
CREATE TABLE translation_search (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    search_word VARCHAR(255) NOT NULL,
    learned_language_id INT NOT NULL,
    search_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (learned_language_id) REFERENCES language(id),

    INDEX idx_user_lang_time (user_id, learned_language_id, search_time DESC)
);
