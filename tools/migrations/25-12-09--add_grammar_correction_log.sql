-- Track grammar/spelling corrections made to simplified articles
-- This allows comparing error rates between different simplification models

CREATE TABLE IF NOT EXISTS grammar_correction_log (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Which article was corrected
    article_id INT NOT NULL,

    -- What field was corrected
    field_type ENUM('TITLE', 'CONTENT', 'SUMMARY') NOT NULL,

    -- The actual correction (before and after)
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,

    -- Language for easier querying
    language_code VARCHAR(10) NOT NULL,

    -- Which model did the simplification (to correlate errors with simplifiers)
    simplification_model VARCHAR(100),

    -- Which model did the correction
    correction_model VARCHAR(100) NOT NULL,

    -- When the correction was made
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key to article
    FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE,

    -- Indexes for common queries
    INDEX idx_article_id (article_id),
    INDEX idx_language_code (language_code),
    INDEX idx_created_at (created_at),
    INDEX idx_simplification_model (simplification_model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
