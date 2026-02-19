-- tools/migrations/26-02-19--add_badge_and_user_badge_tables.sql

CREATE TABLE badge (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon_url VARCHAR(255),
    tier ENUM('bronze', 'silver', 'gold', 'platinum') NOT NULL,
    is_hidden BOOLEAN DEFAULT FALSE,
    is_unique BOOLEAN DEFAULT TRUE
);

CREATE TABLE user_badge (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    badge_id INT NOT NULL,
    achieved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    shown_popup BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (badge_id) REFERENCES badge(id)
);