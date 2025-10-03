-- Add content_simhash column for duplicate detection
-- Using simhash algorithm to detect near-duplicate articles during crawling

ALTER TABLE article
ADD COLUMN content_simhash BIGINT UNSIGNED DEFAULT NULL
COMMENT 'Simhash of article content for duplicate detection';

-- Add index for faster lookup during duplicate checking
CREATE INDEX idx_article_simhash ON article(content_simhash);
