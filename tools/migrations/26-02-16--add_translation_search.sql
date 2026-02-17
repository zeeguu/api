-- Translation search history table
-- Tracks successful searches made in the Translation Tab for history view
-- Only logs when a translation was found (meaning exists)
CREATE TABLE translation_search (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    meaning_id INT NOT NULL,
    search_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (meaning_id) REFERENCES meaning(id),

    INDEX idx_user_time (user_id, search_time DESC)
);
