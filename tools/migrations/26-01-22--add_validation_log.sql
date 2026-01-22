-- Track validation results for analysis
-- Helps understand what kinds of translations are being fixed

CREATE TABLE validation_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    meaning_id INT NOT NULL,
    new_meaning_id INT,
    user_word_id INT,
    action ENUM('valid', 'fixed', 'invalid') NOT NULL,
    reason TEXT,
    context TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (meaning_id) REFERENCES meaning(id),
    FOREIGN KEY (new_meaning_id) REFERENCES meaning(id),
    INDEX idx_action (action),
    INDEX idx_created (created_at)
);
