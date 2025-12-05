-- Add is_admin column to user table for admin dashboard access control
ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
