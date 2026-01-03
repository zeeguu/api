-- Add tokenized_content column to cache full article content with MWE detection
-- This avoids expensive re-tokenization on every article view

ALTER TABLE article_tokenization_cache
ADD COLUMN tokenized_content LONGTEXT DEFAULT NULL;
