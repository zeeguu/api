-- Create article_classification table for flexible content tagging
-- Allows multiple classification types (disturbing, satirical, opinion, etc.)
-- Tracks detection method for analytics and improvement

CREATE TABLE article_classification (
    article_id INT NOT NULL,
    classification_type ENUM('DISTURBING', 'NEGATIVE_NEWS') NOT NULL,
    detection_method ENUM('KEYWORD', 'LLM') NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (article_id, classification_type),
    FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE,
    INDEX idx_classification_type (classification_type),
    INDEX idx_detection_method (detection_method)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

-- Clean up old broken codes (feature was recently deployed, so minimal data loss)
DELETE FROM article_broken_code_map
WHERE broken_code IN ('DISTURBING_CONTENT_PATTERN', 'DISTURBING_CONTENT_LLM');
