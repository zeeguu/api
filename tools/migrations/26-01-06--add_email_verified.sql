-- Add email_verified column to user table
-- Default TRUE for existing users (grandfathered in)
-- Anonymous accounts will be created with FALSE
ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT TRUE;
