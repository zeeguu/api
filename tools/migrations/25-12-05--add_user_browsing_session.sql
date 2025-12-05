-- Create user_browsing_session table for tracking time spent browsing article lists
-- This tracks homepage, search, saved articles, classroom, and other article list pages

CREATE TABLE user_browsing_session (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    page_type VARCHAR(50) NOT NULL,
    start_time DATETIME NOT NULL,
    duration INT DEFAULT 0,
    last_action_time DATETIME,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_browsing_session_user (user_id),
    INDEX idx_browsing_session_start_time (start_time)
);
