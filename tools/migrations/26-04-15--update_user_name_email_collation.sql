-- Update user name and email collation to utf8mb4_unicode_ci
-- This is to match the collation used in the username column
ALTER TABLE user 
MODIFY COLUMN name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
MODIFY COLUMN email VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
