-- Let a teacher decide whether the students of a class see each other.
--
-- Today every member of a class sees the class leaderboard. Defaulting to 1
-- keeps every existing class exactly as it is.

ALTER TABLE cohort
    ADD COLUMN students_see_each_other BOOLEAN NOT NULL DEFAULT 1;
