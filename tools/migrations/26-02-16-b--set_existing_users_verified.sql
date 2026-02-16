-- Set all existing users as email verified
-- Only new users created after this migration will need to verify their email
UPDATE user SET email_verified = TRUE WHERE email_verified IS NULL OR email_verified = FALSE;
