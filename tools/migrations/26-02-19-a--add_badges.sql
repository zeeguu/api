-- tools/migrations/26-02-19--add_badge_and_user_badge_tables.sql

-- Defines the categories of badges that can be earned.
CREATE TABLE badge_category (
    id INT AUTO_INCREMENT PRIMARY KEY,
    metric
        ENUM('TRANSLATED_WORDS', 'CORRECT_EXERCISES', 'COMPLETED_AUDIO_LESSONS',
        'STREAK_DAYS', 'LEARNED_WORDS', 'READ_ARTICLES', 'FRIENDS') UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    award_mechanism ENUM('COUNTER', 'GAUGE', 'ONE_TIME') NOT NULL
);

-- Defines specific badges, organized as levels within a badge category (like bronze/silver/gold).
CREATE TABLE badge (
    id INT AUTO_INCREMENT PRIMARY KEY,
    badge_category_id INT NOT NULL,
    level INT NOT NULL,
    threshold INT NOT NULL,
    name VARCHAR(100),
    description TEXT,
    icon_name VARCHAR(255),
    UNIQUE(badge_category_id, level),
    FOREIGN KEY (badge_category_id) REFERENCES badge_category(id)
);

-- Tracks which badges each user has earned.
CREATE TABLE user_badge (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    badge_id INT NOT NULL,
    achieved_at DATETIME DEFAULT NULL,
    is_shown BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (badge_id) REFERENCES badge(id)
);

-- Tracks each user's current value for each badge category (used to check against badge thresholds).
CREATE TABLE user_badge_progress (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    badge_category_id INT NOT NULL,
    value INT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE(user_id, badge_category_id),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (badge_category_id) REFERENCES badge_category(id)
);
