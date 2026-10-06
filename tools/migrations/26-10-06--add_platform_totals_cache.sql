-- Last computed totals for /stats/totals (the research page), shared by all
-- workers so a restart does not make each of them recompute. A single row.

CREATE TABLE IF NOT EXISTS platform_totals_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `totals_json` TEXT NOT NULL,
    `computed_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
