-- friend table
-- user_a_id always holds the smaller user id (canonical order enforced at application level)
CREATE TABLE friend (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_a_id INT NOT NULL,
    user_b_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME,
    friend_streak INT DEFAULT 0,
    friend_streak_last_updated DATETIME,
    FOREIGN KEY (user_a_id) REFERENCES user(id),
    FOREIGN KEY (user_b_id) REFERENCES user(id)
);

-- Friend request table
CREATE TABLE friend_request (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME,
    FOREIGN KEY (sender_id) REFERENCES user(id),
    FOREIGN KEY (receiver_id) REFERENCES user(id)
);
