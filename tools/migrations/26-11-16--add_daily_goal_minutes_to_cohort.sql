-- A class can set the daily goal of its members (ADR 046): a study cohort that
-- asks for 10 minutes a day gets its members counted against 10, not the
-- default 5. Set when a learner joins the class; NULL (every existing class)
-- leaves the learner's goal alone.

ALTER TABLE cohort
    ADD COLUMN daily_goal_minutes INT NULL;

-- The Danish challenge (cohort 1 and the group from 16 Nov): 10 minutes a day.
-- Their current members were set to 10 by hand on 2026-11-16.
UPDATE cohort SET daily_goal_minutes = 10 WHERE id IN (605, 607);
