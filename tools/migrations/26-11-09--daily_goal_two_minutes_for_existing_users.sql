-- ADR 046: the streak is now counted against the learner's daily goal
-- (user_preference 'daily_goal_minutes', default 10) instead of a fixed
-- 2 minutes. Learners who signed up before that keep 2, so no streak breaks
-- on the day this ships; they can raise it in Language Settings.
--
-- Run BEFORE deploying the API: once the new code runs, a learner without
-- the preference is counted against 10 minutes.
INSERT INTO user_preference (user_id, `key`, value)
SELECT u.id, 'daily_goal_minutes', '2'
FROM `user` AS u
WHERE u.id NOT IN (SELECT user_id FROM user_preference WHERE `key` = 'daily_goal_minutes');
