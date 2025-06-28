-- TODO: This script does not include adding the user_word to the basic_sr_schedule.
-- TODO: Could it be that it got added by SQLAlchemy? Otherwise make sure to add it here below.


-- Step 1: Create the new UserWord table

CREATE TABLE user_word
(
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    user_id               INT       NOT NULL,
    meaning_id            INT       NOT NULL,
    -- untested code... this preferred_bookmark_id
    preferred_bookmark_id INT       NULL,
    fit_for_study         BOOLEAN DEFAULT TRUE,
    user_preference       TEXT      NULL,
    level                 INT       NULL,
    learned_time          TIMESTAMP NULL,

    -- Foreign key constraints
    FOREIGN KEY (user_id) REFERENCES User (id) ON DELETE CASCADE,
    FOREIGN KEY (meaning_id) REFERENCES Meaning (id),
    -- untested FK
    FOREIGN KEY (preferred_bookmark_id) REFERENCES Bookmark (id),

    -- Unique constraint to prevent duplicate user-word pairs
    CONSTRAINT unique_user_word UNIQUE (user_id, meaning_id)
);

# temporary;


-- Step 2: Migrate data from Bookmark to UserWord
INSERT INTO user_word (user_id, meaning_id, learned_time, level, preferred_bookmark_id, fit_for_study,
                       user_preference)
SELECT user_id,
       meaning_id,
       max(learned_time),
       max(level),
       max(id), -- untested; adding the last bookmark - as good as any i guess?
       min(fit_for_study),
       min(user_preference)
FROM Bookmark
group by user_id, meaning_id;

-- Step 3: Update Bookmark table to reference UserWord
-- First, add the new foreign key column
ALTER TABLE bookmark
    ADD COLUMN user_word_id INT NULL;


-- Step 4: Update the bookmark records to reference the new UserWord records
UPDATE Bookmark b
    INNER JOIN user_word uw ON b.user_id = uw.user_id AND b.meaning_id = uw.meaning_id
SET b.user_word_id = uw.id;



# SHOW CREATE TABLE Bookmark;
# use this if you need to drop more foreign key constraints;
# i might have deleted one more from the UI while running this in dev

ALTER TABLE Bookmark
    DROP FOREIGN KEY bookmark_ibfk_3;
ALTER TABLE Bookmark
    DROP FOREIGN KEY meaning_id_ibfk;

-- Step 5: Drop the old columns from Bookmark (after verifying the migration worked)
-- WARNING: Only run these after confirming the data migration is correct!
ALTER TABLE Bookmark
    DROP COLUMN learned_time,
    DROP COLUMN level,
    DROP COLUMN fit_for_study,
    DROP COLUMN user_preference,
    DROP COLUMN user_id,
    DROP COLUMN meaning_id;

-- Step 6: Add foreign key constraint for the new relationship
ALTER TABLE Bookmark
    ADD CONSTRAINT fk_bookmark_user_word
        FOREIGN KEY (user_word_id) REFERENCES user_word (id) ON DELETE CASCADE;

-- Step 7: Make user_word_id NOT NULL (after confirming all records have been updated)
ALTER TABLE Bookmark
    MODIFY COLUMN user_word_id INT NOT NULL;


-- Step 8: Migrating the bookmark-exercise-mapping
-- as far as I can tell, all we need is for every exercise to
-- assign to it the meaning that it was about; and we can simply add one more column to the
-- exercise (user_word_id) - then, getting the history for a given meaning is as simple as selecting
-- in the exercise table

alter table exercise
    add column user_word_id int not null;

select count(*)
from exercise; -- 484.457

select e.id, b.user_word_id, e.source_id, e.solving_speed
from exercise e
         join bookmark_exercise_mapping bem on bem.exercise_id = e.id
         join Bookmark b on b.id = bem.bookmark_id
order by id desc
limit 10;

# exercise_id user_word_id
#485149	327744	5	3000
#485148	327581	22	1000
#485147	328078	22	3000
#485146	327536	23	2000
#485145	327685	5	2000
#485144	327744	5	0
#485143	327463	25	0
#485142	327744	5	3000
#485140	328377	6	5000
#485139	327524	6	3000

update exercise e
    join bookmark_exercise_mapping bem on bem.exercise_id = e.id
    join bookmark b on b.id = bem.bookmark_id
set e.user_word_id = b.user_word_id;

select id, user_word_id
from exercise
order by id desc
limit 11;

#485149	327744
#485148	327581
#485147	328078
#485146	327536
#485145	327685
#485144	327744
#485143	327463
#485142	327744
#485141	0
#485140	328377

# Problem, we seem to have exercise IDs that don't have a BEM
# they will result in a 0 in the user_word_id
# The only way I can imagine this happening is when one deletes a bookmark
# and that triggers a delete in BEM but that does not cascade into e...
#
# For now, we drop all the lines that have 0 in user_word_id

select count(*)
from exercise
where user_word_id = 0; -- 116,574

delete
from exercise
where user_word_id = 0;


alter table exercise
    add constraint fk_exercise_user_word
        FOREIGN KEY (user_word_id) REFERENCES user_word (id);

-- now we can drop the bookmark_exercise_mapping
drop table bookmark_exercise_mapping;


-- Step 9: Migrate basic_sr_schedule from bookmark_id to user_word_id
-- Add user_word_id column to basic_sr_schedule
alter table basic_sr_schedule
    add column user_word_id int null after id;

-- Update basic_sr_schedule to reference user_word instead of bookmark
update basic_sr_schedule bsr
    join bookmark b on b.id = bsr.bookmark_id
set bsr.user_word_id = b.user_word_id;

-- Add foreign key constraint for user_word_id
alter table basic_sr_schedule
    add constraint fk_basic_sr_schedule_user_word
        foreign key (user_word_id) references user_word (id) on delete cascade;

-- Make user_word_id NOT NULL (after confirming all records have been updated)
alter table basic_sr_schedule
    modify column user_word_id int not null;

-- Drop the old bookmark_id column and its foreign key
alter table basic_sr_schedule
    drop foreign key basic_sr_schedule_ibfk_1;

alter table basic_sr_schedule
    drop column bookmark_id;

-- Step 10: Remove duplicate basic_sr_schedule records
-- Keep only the record for the user_word with the highest level
-- If level is the same, keep the one with the highest id (most recent)
DELETE bsr1
FROM basic_sr_schedule bsr1
         INNER JOIN basic_sr_schedule bsr2
         INNER JOIN user_word uw1 ON bsr1.user_word_id = uw1.id
         INNER JOIN user_word uw2 ON bsr2.user_word_id = uw2.id
WHERE bsr1.user_word_id = bsr2.user_word_id
  AND (uw1.level < uw2.level
    OR (uw1.level = uw2.level AND bsr1.id < bsr2.id));

-- Add unique constraint to prevent future duplicates
alter table basic_sr_schedule
    add constraint unique_user_word_schedule unique (user_word_id);
