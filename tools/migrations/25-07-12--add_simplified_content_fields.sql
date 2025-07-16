-- Add simplified article relationship fields
-- This migration enables creating separate article entities for different CEFR levels
-- Each simplified article points to its parent and has its own metrics

-- Add simplified article fields to article table
ALTER TABLE article
    ADD COLUMN parent_article_id          INT                                       DEFAULT NULL COMMENT 'ID of the parent article (NULL for original articles)',
    ADD COLUMN cefr_level                 ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2') DEFAULT NULL COMMENT 'CEFR level of this article version (original level for parent articles, simplified level for children)',
    ADD COLUMN simplification_ai_model_id INT                                       DEFAULT NULL COMMENT 'AI model used for generating this simplification',
    ADD FOREIGN KEY (parent_article_id) REFERENCES article (id) ON DELETE CASCADE,
    ADD FOREIGN KEY (simplification_ai_model_id) REFERENCES ai_models (id);
