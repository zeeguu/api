-- Step 3 of 3: Enforce NOT NULL and add UNIQUE constraint on username.
-- This must be run AFTER 26-02-24-b--add_username.py has populated all usernames.
ALTER TABLE user
MODIFY username VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL;

ALTER TABLE user
ADD CONSTRAINT unique_username UNIQUE (username);
