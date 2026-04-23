CREATE TABLE user_avatar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    image_name VARCHAR(100),
    character_color VARCHAR(7),
    background_color VARCHAR(7),
    UNIQUE(user_id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);
