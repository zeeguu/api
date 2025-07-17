-- Remove duplicate articles based on title, content, and source
-- This migration addresses the issue where articles with identical content
-- but no URL were being saved multiple times, bypassing URL-based deduplication

-- Increase GROUP_CONCAT limit to handle large groups of duplicates
SET SESSION group_concat_max_len = 100000;

-- First, let's create a temporary table to identify duplicates
CREATE TEMPORARY TABLE duplicate_articles AS
SELECT 
    title,
    source_id,
    feed_id,
    language_id,
    SUBSTRING(content, 1, 1000) as content_hash,
    COUNT(*) as duplicate_count,
    MIN(id) as keep_id,
    GROUP_CONCAT(id ORDER BY id) as all_ids
FROM article 
WHERE parent_article_id IS NULL  -- Only original articles
GROUP BY title, source_id, feed_id, language_id, SUBSTRING(content, 1, 1000)
HAVING COUNT(*) > 1;

-- Show statistics before cleanup
SELECT 
    COUNT(*) as total_duplicate_groups,
    SUM(duplicate_count) as total_duplicate_articles,
    SUM(duplicate_count - 1) as articles_to_remove
FROM duplicate_articles;

-- Create a temporary table with all article IDs to be removed (excluding the ones we keep)
CREATE TEMPORARY TABLE articles_to_remove AS
SELECT id as article_id
FROM article a
WHERE parent_article_id IS NULL
AND EXISTS (
    SELECT 1 FROM duplicate_articles da
    WHERE a.title = da.title 
    AND a.source_id = da.source_id 
    AND a.feed_id = da.feed_id 
    AND a.language_id = da.language_id
    AND SUBSTRING(a.content, 1, 1000) = da.content_hash
    AND a.id != da.keep_id
);

-- Before deleting, let's update all references to point to the kept articles
-- This is critical to maintain referential integrity

-- 1. Update simplified articles to point to kept parent articles
-- First create a mapping of old parent IDs to new parent IDs
CREATE TABLE parent_mapping_temp AS
SELECT 
    parent.id as old_parent_id,
    da.keep_id as new_parent_id
FROM article parent
JOIN duplicate_articles da ON (
    parent.title = da.title 
    AND parent.source_id = da.source_id 
    AND parent.feed_id = da.feed_id 
    AND parent.language_id = da.language_id
    AND SUBSTRING(parent.content, 1, 1000) = da.content_hash
)
WHERE parent.id IN (SELECT article_id FROM articles_to_remove);

-- Now update the parent_article_id references
UPDATE article 
SET parent_article_id = (
    SELECT new_parent_id 
    FROM parent_mapping_temp 
    WHERE old_parent_id = article.parent_article_id
)
WHERE parent_article_id IN (SELECT old_parent_id FROM parent_mapping_temp);

-- 2. Update user_article table
-- Use INSERT IGNORE to handle duplicates
CREATE TABLE user_article_temp AS
SELECT DISTINCT
    u.user_id,
    da.keep_id as article_id,
    u.starred,
    u.opened,
    u.liked
FROM user_article u
JOIN articles_to_remove atr ON u.article_id = atr.article_id
JOIN article a ON a.id = atr.article_id
JOIN duplicate_articles da ON (
    a.title = da.title 
    AND a.source_id = da.source_id 
    AND a.feed_id = da.feed_id 
    AND a.language_id = da.language_id
    AND SUBSTRING(a.content, 1, 1000) = da.content_hash
);

-- Remove old entries that will be replaced
DELETE u FROM user_article u
JOIN articles_to_remove atr ON u.article_id = atr.article_id;

-- Insert the updated entries, avoiding duplicates with existing data
INSERT IGNORE INTO user_article (user_id, article_id, starred, opened, liked)
SELECT user_id, article_id, starred, opened, liked
FROM user_article_temp temp
WHERE NOT EXISTS (
    SELECT 1 FROM user_article existing 
    WHERE existing.user_id = temp.user_id 
    AND existing.article_id = temp.article_id
);

-- Clean up
DROP TABLE user_article_temp;

-- 3. Update other tables by deleting entries that reference articles to be removed
-- These will be handled by foreign key constraints or are less critical
DELETE FROM cohort_article_map WHERE article_id IN (SELECT article_id FROM articles_to_remove);
DELETE FROM article_difficulty_feedback WHERE article_id IN (SELECT article_id FROM articles_to_remove);
DELETE FROM personal_copy WHERE article_id IN (SELECT article_id FROM articles_to_remove);
DELETE FROM article_topic_map WHERE article_id IN (SELECT article_id FROM articles_to_remove);
DELETE FROM article_url_keyword_map WHERE article_id IN (SELECT article_id FROM articles_to_remove);
DELETE FROM article_broken_code_map WHERE article_id IN (SELECT article_id FROM articles_to_remove);
DELETE FROM article_topic_user_feedback WHERE article_id IN (SELECT article_id FROM articles_to_remove);

-- Now we can safely delete the duplicate articles
DELETE FROM article 
WHERE id IN (SELECT article_id FROM articles_to_remove);

-- Clean up temporary tables
DROP TEMPORARY TABLE duplicate_articles;
DROP TEMPORARY TABLE articles_to_remove;
DROP TABLE parent_mapping_temp;

-- Show final statistics
SELECT 
    COUNT(*) as remaining_articles,
    COUNT(DISTINCT title, source_id, feed_id, language_id, SUBSTRING(content, 1, 1000)) as unique_articles
FROM article 
WHERE parent_article_id IS NULL;

-- Show specific statistics for the "As crianças devem ser" articles
SELECT 
    COUNT(*) as remaining_criancas_articles
FROM article 
WHERE title LIKE 'As crianças devem ser%' 
AND parent_article_id IS NULL;