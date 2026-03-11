ALTER TABLE user
ADD COLUMN username VARCHAR(50);

-- This is maybe needed
-- SET SQL_SAFE_UPDATES = 0;

-- Option 1 user_<id>
UPDATE user
SET username = CONCAT('user_', id)
WHERE id IS NOT NULL
AND username IS NULL;

-- In that case remember to enable it again
SET SQL_SAFE_UPDATES = 1;

-- Change the column to be not null and unique
ALTER TABLE user
MODIFY username VARCHAR(50) NOT NULL;

ALTER TABLE user
ADD CONSTRAINT unique_username UNIQUE (username);