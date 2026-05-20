-- Track when each PersonalCopy was created, so the My Articles surface can
-- render "Saved 2h ago" instead of falling back to the article's publish time
-- (which is misleading on a save-sorted list).
--
-- New rows default to CURRENT_TIMESTAMP via the DB.
-- Existing rows are backfilled from article.published_time as the best
-- available proxy — most saves happen near publish, and any error is
-- bounded by article age.

ALTER TABLE personal_copy
ADD COLUMN saved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP;

UPDATE personal_copy pc
JOIN article a ON a.id = pc.article_id
SET pc.saved_at = a.published_time
WHERE a.published_time IS NOT NULL;
