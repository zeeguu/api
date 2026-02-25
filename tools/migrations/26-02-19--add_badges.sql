-- tools/migrations/26-02-19--add_badge_and_user_badge_tables.sql

CREATE TABLE badge (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT, -- We could store a template string, and would interpolate the target values.
    is_hidden BOOLEAN DEFAULT FALSE
    UNIQUE(code)
);

CREATE TABLE badge_level (
    id INT AUTO_INCREMENT PRIMARY KEY,
    badge_id INT NOT NULL,
    name VARCHAR(100),
    level INT NOT NULL,
    target_value INT NOT NULL,
    icon_url VARCHAR(255),
    UNIQUE(badge_id, level),
    FOREIGN KEY (badge_id) REFERENCES badge(id)
);

CREATE TABLE user_badge_level (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    badge_level_id INT NOT NULL,
    achieved_at DATETIME DEFAULT NULL,
    is_shown BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, badge_level_id),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (badge_level_id) REFERENCES badge_level(id)
);