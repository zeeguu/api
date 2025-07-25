-- Add completion tracking fields to user_article table
-- reading_completion: stores current percentage to avoid expensive recalculation  
-- completed_at: marks completion and prevents duplicate notifications

ALTER TABLE user_article 
ADD COLUMN reading_completion FLOAT DEFAULT 0.0 
COMMENT 'Current reading completion percentage (0.0 to 1.0) updated on scroll events',
ADD COLUMN completed_at DATETIME DEFAULT NULL 
COMMENT 'When the user completed reading (>90%) - also prevents duplicate notifications';