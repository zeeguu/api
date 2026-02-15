CREATE TABLE exercise_report (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    bookmark_id INT NOT NULL,
    exercise_source_id INT NOT NULL,
    reason ENUM('word_not_shown', 'wrong_highlighting', 'context_confusing', 'wrong_translation', 'context_wrong', 'other') NOT NULL,
    comment TEXT DEFAULT NULL,
    context_used TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (bookmark_id) REFERENCES bookmark(id),
    FOREIGN KEY (exercise_source_id) REFERENCES exercise_source(id),
    UNIQUE KEY unique_user_bookmark_source (user_id, bookmark_id, exercise_source_id)
);
