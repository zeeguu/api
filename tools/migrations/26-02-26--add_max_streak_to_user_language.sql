-- Add max_streak tracking to user_language table
ALTER TABLE user_language
ADD COLUMN max_streak INT NOT NULL DEFAULT 0,
ADD COLUMN max_streak_date DATETIME NULL;

-- Seed max_streak from current daily_streak for users with active streaks
UPDATE user_language
SET max_streak = daily_streak,
    max_streak_date = last_practiced
WHERE daily_streak > 0;
