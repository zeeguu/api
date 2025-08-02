-- Add last_seen column to users table for tracking user activity
-- This will be used to filter batch operations to only active users
-- Updates once per day maximum to minimize database writes

ALTER TABLE user 
ADD COLUMN last_seen DATETIME DEFAULT NULL 
COMMENT 'Date of last user activity (updated once per day maximum)';

-- Add index for efficient querying by date ranges
CREATE INDEX idx_user_last_seen ON user(last_seen);

-- Populate existing users with their most recent bookmark date
-- This gives us accurate activity data for existing users
UPDATE user u 
SET last_seen = (
    SELECT MAX(b.time) 
    FROM bookmark b 
    JOIN user_word uw ON b.user_word_id = uw.id 
    WHERE uw.user_id = u.id
) 
WHERE last_seen IS NULL 
AND EXISTS (
    SELECT 1 
    FROM bookmark b 
    JOIN user_word uw ON b.user_word_id = uw.id 
    WHERE uw.user_id = u.id
);