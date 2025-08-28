-- Add translation_source field to bookmark table to track where the translation came from
ALTER TABLE bookmark 
ADD COLUMN translation_source ENUM('reading', 'exercise', 'article_preview') 
DEFAULT 'reading' 
COMMENT 'Tracks where this bookmark/translation was created: reading (full article), exercise, or article_preview (home page summaries)';