-- Create table to track user reports of broken articles
-- When USER_REPORT_THRESHOLD (3) users report an article, it's marked as USER_REPORTED

CREATE TABLE IF NOT EXISTS user_article_broken_report (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    article_id INT NOT NULL,
    report_time DATETIME NOT NULL,
    reason VARCHAR(255),

    -- One report per user per article
    CONSTRAINT user_article_unique UNIQUE (user_id, article_id),

    -- Foreign keys
    CONSTRAINT fk_user_broken_report_user
        FOREIGN KEY (user_id) REFERENCES user(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_user_broken_report_article
        FOREIGN KEY (article_id) REFERENCES article(id)
        ON DELETE CASCADE,

    -- Indexes for common queries
    INDEX idx_article_id (article_id),
    INDEX idx_user_id (user_id),
    INDEX idx_report_time (report_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
