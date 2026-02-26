-- Add per-language streak tracking columns to user_language table
ALTER TABLE user_language
ADD COLUMN last_practiced DATETIME NULL,
ADD COLUMN daily_streak INT NOT NULL DEFAULT 0;

-- Migrate existing global streaks to user's current learned_language
UPDATE user_language ul
JOIN user u ON ul.user_id = u.id AND ul.language_id = u.learned_language_id
SET ul.daily_streak = u.daily_streak,
    ul.last_practiced = u.last_seen
WHERE u.daily_streak > 0;
