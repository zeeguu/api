-- Add article_type column to classify articles as news (current events) or general interest (evergreen)
-- Starting Dec 2024, this is classified by LLM during article simplification

ALTER TABLE article
ADD COLUMN article_type ENUM('news', 'general') DEFAULT NULL
COMMENT 'Article type: news (current events, time-sensitive) or general (evergreen, read anytime)';
