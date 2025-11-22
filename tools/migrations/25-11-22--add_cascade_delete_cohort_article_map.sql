-- Add ON DELETE CASCADE to cohort_article_map foreign key
-- This ensures that when an article is deleted, its cohort mappings are automatically removed
-- preventing orphaned records that cause NoneType errors

-- First, clean up any existing orphaned records where article_id points to deleted articles
DELETE FROM cohort_article_map
WHERE article_id NOT IN (SELECT id FROM article);

-- Drop the existing foreign key constraint
ALTER TABLE cohort_article_map
DROP FOREIGN KEY cohort_article_map_ibfk_2;

-- Re-add the foreign key with CASCADE delete
ALTER TABLE cohort_article_map
ADD CONSTRAINT cohort_article_map_ibfk_2
FOREIGN KEY (article_id) REFERENCES article(id)
ON DELETE CASCADE;
