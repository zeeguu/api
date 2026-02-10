-- Cache table for monthly activity statistics by type
-- Historical months are cached permanently, current month refreshed periodically

CREATE TABLE IF NOT EXISTS monthly_activity_stats_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `year_month` VARCHAR(7) NOT NULL UNIQUE COMMENT 'Format: YYYY-MM',
    `exercise_minutes` INT NOT NULL DEFAULT 0,
    `reading_minutes` INT NOT NULL DEFAULT 0,
    `browsing_minutes` INT NOT NULL DEFAULT 0,
    `audio_minutes` INT NOT NULL DEFAULT 0,
    `computed_at` DATETIME NOT NULL,
    INDEX idx_year_month (`year_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
