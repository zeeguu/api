-- Add table for tracking audio lesson generation progress
-- Enables real-time UI updates during lesson generation
-- Only one generation per user at a time is allowed

CREATE TABLE audio_lesson_generation_progress (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    status ENUM('pending', 'generating_script', 'synthesizing_audio', 'combining_audio', 'done', 'error') DEFAULT 'pending',
    current_step INT DEFAULT 0,
    total_steps INT DEFAULT 0,
    message VARCHAR(255) DEFAULT NULL,
    current_word INT DEFAULT 0,
    total_words INT DEFAULT 0,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
