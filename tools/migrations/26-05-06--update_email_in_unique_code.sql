-- Before this migration the email in 'unique_code' was case sensitive
-- This migration updates the collation for the email to utf8mb4_unicode_ci 
ALTER TABLE unique_code MODIFY email VARCHAR(255) 
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;