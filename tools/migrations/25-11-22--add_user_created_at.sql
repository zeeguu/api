-- Add created_at timestamp to user table
ALTER TABLE user
ADD COLUMN created_at DATETIME DEFAULT NULL
COMMENT 'Timestamp when the user account was created';
