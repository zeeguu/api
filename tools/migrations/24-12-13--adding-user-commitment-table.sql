CREATE TABLE user_commitment (
    user_id INT PRIMARY KEY,
    user_minutes INT DEFAULT 0,
    user_days INT DEFAULT 0,
    consecutive_weeks INT DEFAULT 0,
    commitment_last_updated datetime,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);