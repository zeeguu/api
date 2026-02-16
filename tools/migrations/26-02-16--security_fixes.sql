-- Security fixes migration
-- 1. Expand unique_code.code column to support 6-char alphanumeric codes (was 4 chars for 3-digit codes)
-- 2. Expand user.password column to support bcrypt hashes (60 chars)

-- Expand unique_code.code from VARCHAR(4) to VARCHAR(6) for alphanumeric codes
ALTER TABLE unique_code MODIFY COLUMN code VARCHAR(6);

-- Expand user.password column to support bcrypt hashes (60 chars)
-- Current SHA1 hashes are 40 chars, bcrypt is 60 chars
ALTER TABLE user MODIFY COLUMN password VARCHAR(255);

-- Note: Existing users with SHA1 hashes will be automatically migrated to bcrypt
-- on their next successful login.
