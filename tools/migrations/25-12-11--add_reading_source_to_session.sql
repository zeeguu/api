-- Add reading_source column to user_reading_session to track where article was opened
-- Values: 'extension' or 'web' (NULL for historical data)
ALTER TABLE user_reading_session
ADD COLUMN reading_source VARCHAR(20) DEFAULT NULL;
