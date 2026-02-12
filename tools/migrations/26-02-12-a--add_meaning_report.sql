-- Reports for AI-generated content (examples, explanations) at the meaning level
CREATE TABLE IF NOT EXISTS meaning_report (
    id INT AUTO_INCREMENT PRIMARY KEY,
    meaning_id INT NOT NULL,
    user_id INT NOT NULL,
    reason ENUM('bad_examples', 'wrong_meaning', 'wrong_level', 'other') NOT NULL,
    comment TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (meaning_id) REFERENCES meaning(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_meaning_report_meaning (meaning_id),
    INDEX idx_meaning_report_unresolved (resolved, created_at)
);
