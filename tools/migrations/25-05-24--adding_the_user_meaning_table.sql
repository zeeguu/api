-- Step 1: Create the new UserMeaning table

CREATE TABLE UserMeaning
(
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT       NOT NULL,
    meaning_id      INT       NOT NULL,
    learned_time    TIMESTAMP NULL,
    level           INT       NULL,
    fit_for_study   BOOLEAN DEFAULT TRUE,
    user_preference TEXT      NULL,
    too_easy        TIMESTAMP NULL,

    -- Foreign key constraints
    FOREIGN KEY (user_id) REFERENCES User (id) ON DELETE CASCADE,
    FOREIGN KEY (meaning_id) REFERENCES Meaning (id) ON DELETE CASCADE,

    -- Unique constraint to prevent duplicate user-meaning pairs
    UNIQUE KEY unique_user_meaning (user_id, meaning_id)
);

-- Step 2: Migrate data from Bookmark to UserMeaning
INSERT INTO UserMeaning (user_id, meaning_id, learned_time, level, learning_cycle, fit_for_study, user_preference)
SELECT user_id,
       meaning_id,
       learned_time,
       level,
       learning_cycle,
       fit_for_study,
       user_preference
FROM Bookmark;

-- Step 3: Update Bookmark table to reference UserMeaning
-- First, add the new foreign key column
ALTER TABLE Bookmark
    ADD COLUMN user_meaning_id INT NULL;

-- Step 4: Update the bookmark records to reference the new UserMeaning records
UPDATE Bookmark b
    INNER JOIN UserMeaning um ON b.user_id = um.user_id AND b.meaning_id = um.meaning_id
SET b.user_meaning_id = um.id;

-- Step 5: Drop the old columns from Bookmark (after verifying the migration worked)
-- WARNING: Only run these after confirming the data migration is correct!
ALTER TABLE Bookmark
    DROP COLUMN learned_time,
    DROP COLUMN level,
    DROP COLUMN learning_cycle,
    DROP COLUMN fit_for_study,
    DROP COLUMN user_preference,
    DROP COLUMN user_id,
    DROP COLUMN meaning_id;

-- Step 6: Add foreign key constraint for the new relationship
ALTER TABLE Bookmark
    ADD CONSTRAINT fk_bookmark_user_meaning
        FOREIGN KEY (user_meaning_id) REFERENCES UserMeaning (id) ON DELETE CASCADE;

-- Step 7: Make user_meaning_id NOT NULL (after confirming all records have been updated)
ALTER TABLE Bookmark
    MODIFY COLUMN user_meaning_id INT NOT NULL;