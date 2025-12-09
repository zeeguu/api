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

    -- Language
    language_id INT NOT NULL,

    -- Which model did the simplification (to correlate errors with simplifiers)
    simplification_ai_generator_id INT,

    -- Which model did the correction
    correction_ai_generator_id INT NOT NULL,

    -- When the correction was made
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE,
    FOREIGN KEY (language_id) REFERENCES language(id),
    FOREIGN KEY (simplification_ai_generator_id) REFERENCES ai_generator(id),
    FOREIGN KEY (correction_ai_generator_id) REFERENCES ai_generator(id),

    -- Indexes for common queries
    INDEX idx_article_id (article_id),
    INDEX idx_language_id (language_id),
    INDEX idx_created_at (created_at),
    INDEX idx_simplification_ai_generator_id (simplification_ai_generator_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
