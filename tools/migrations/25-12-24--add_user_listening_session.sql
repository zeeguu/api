-- Create user_listening_session table for tracking time spent listening to audio lessons

CREATE TABLE user_listening_session (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    daily_audio_lesson_id INT NOT NULL,
    start_time DATETIME NOT NULL,
    duration INT DEFAULT 0,  -- milliseconds
    last_action_time DATETIME,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (daily_audio_lesson_id) REFERENCES daily_audio_lesson(id) ON DELETE CASCADE,
    INDEX idx_listening_session_user (user_id),
    INDEX idx_listening_session_start_time (start_time),
    INDEX idx_listening_session_lesson (daily_audio_lesson_id)
);
