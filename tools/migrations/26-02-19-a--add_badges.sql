-- tools/migrations/26-02-19--add_badge_and_user_badge_tables.sql

-- Defines the types of activities that can earn badges.
CREATE TABLE activity_type (
    id INT AUTO_INCREMENT PRIMARY KEY,
    metric
        ENUM('TRANSLATED_WORDS', 'CORRECT_EXERCISES', 'COMPLETED_AUDIO_LESSONS',
        'STREAK_DAYS', 'LEARNED_WORDS', 'READ_ARTICLES', 'FRIENDS') UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    badge_type ENUM('COUNTER', 'GAUGE', 'ONE_TIME') NOT NULL
);

-- Defines specific badges, organized as levels within an activity type (like bronze/silver/gold).
CREATE TABLE badge (
    id INT AUTO_INCREMENT PRIMARY KEY,
    activity_type_id INT NOT NULL,
    level INT NOT NULL,
    threshold INT NOT NULL,
    name VARCHAR(100),
    icon_name VARCHAR(255),
    UNIQUE(activity_type_id, level),
    FOREIGN KEY (activity_type_id) REFERENCES activity_type(id)
);

-- Tracks which badges each user has earned.
CREATE TABLE user_badge (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    badge_id INT NOT NULL,
    achieved_at DATETIME DEFAULT NULL,
    is_shown BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (badge_id) REFERENCES badge(id)
);

-- Tracks each user's current value for each activity type (used to check against badge thresholds).
CREATE TABLE user_metric (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    activity_type_id INT NOT NULL,
    value INT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE(user_id, activity_type_id),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (activity_type_id) REFERENCES activity_type(id)
);
