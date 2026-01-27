CREATE TABLE user_word_interaction_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_word_id INT NOT NULL,
    interaction_type VARCHAR(50) NOT NULL,
    event_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_word_id) REFERENCES user_word(id),
    INDEX idx_user_word (user_word_id),
    INDEX idx_interaction_type (interaction_type)
) CHARACTER SET utf8mb4;
