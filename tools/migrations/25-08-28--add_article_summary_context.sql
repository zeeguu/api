-- Create article_summary_context table to allow bookmarks from article summaries
-- This enables users to translate words/phrases from article summaries

CREATE TABLE IF NOT EXISTS `article_summary_context` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `bookmark_id` int(11) NOT NULL,
  `article_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `bookmark_id` (`bookmark_id`),
  KEY `article_id` (`article_id`),
  CONSTRAINT `article_summary_context_ibfk_1` FOREIGN KEY (`bookmark_id`) REFERENCES `bookmark` (`id`),
  CONSTRAINT `article_summary_context_ibfk_2` FOREIGN KEY (`article_id`) REFERENCES `article` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- Add index for performance when querying bookmarks by article
CREATE INDEX `idx_article_summary_context_article_bookmark` ON `article_summary_context` (`article_id`, `bookmark_id`);