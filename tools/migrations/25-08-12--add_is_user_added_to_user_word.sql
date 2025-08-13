-- Add is_user_added column to track manually added words by users
ALTER TABLE user_word 
ADD COLUMN is_user_added BOOLEAN DEFAULT FALSE 
COMMENT 'Indicates if this word was manually added by the user rather than from article translation';

-- Set default value for existing records
UPDATE user_word SET is_user_added = FALSE WHERE is_user_added IS NULL;