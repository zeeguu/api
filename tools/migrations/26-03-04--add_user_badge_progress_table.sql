-- tools/migrations/26-03-04--add_user_badge_progress_table.sql

CREATE TABLE user_badge_progress (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    badge_id INT NOT NULL,
    current_value INT NOT NULL,
    UNIQUE(user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (badge_id) REFERENCES badge(id)
);