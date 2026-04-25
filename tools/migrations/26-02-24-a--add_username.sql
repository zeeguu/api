-- Step 1 of 3: Add nullable username column.
-- After this, run 26-02-24-b--add_username.py to populate usernames.
-- Then run 26-02-24-c--add_username.sql to enforce NOT NULL + UNIQUE.
ALTER TABLE user
ADD COLUMN username VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
