-- Add hidden column to UserArticle table to allow users to hide articles
ALTER TABLE user_article 
ADD COLUMN hidden DATETIME DEFAULT NULL;