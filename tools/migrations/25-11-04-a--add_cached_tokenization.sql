-- Create separate table for cached tokenization to avoid bloating article table
-- 1-to-1 relationship with article table
CREATE TABLE IF NOT EXISTS article_tokenization_cache (
    article_id INT PRIMARY KEY,
    tokenized_summary MEDIUMTEXT DEFAULT NULL COMMENT 'JSON-encoded tokenized summary (Stanza tokens)',
    tokenized_title TEXT DEFAULT NULL COMMENT 'JSON-encoded tokenized title (Stanza tokens)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
