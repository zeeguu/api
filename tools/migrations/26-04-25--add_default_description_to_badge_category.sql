-- Add default descriptions for badge categories (singular + plural forms)
-- These are used as fallback templates when a specific badge level
-- is not yet achieved. They support {threshold} substitution for progress display.

ALTER TABLE badge_category ADD COLUMN singular_default_description TEXT DEFAULT NULL;
ALTER TABLE badge_category ADD COLUMN plural_default_description TEXT DEFAULT NULL;

UPDATE badge_category
SET
  singular_default_description = CASE id
    WHEN 1 THEN 'Translate a unique word while reading.'
    WHEN 2 THEN 'Solve an exercise correctly.'
    WHEN 3 THEN 'Complete an audio lesson.'
    WHEN 4 THEN 'Maintain a streak for a day.'
    WHEN 5 THEN 'Learn a new word.'
    WHEN 6 THEN 'Read an article.'
    WHEN 7 THEN 'Add a friend.'
  END,

  plural_default_description = CASE id
    WHEN 1 THEN 'Translate {threshold} unique words while reading.'
    WHEN 2 THEN 'Solve {threshold} exercises correctly.'
    WHEN 3 THEN 'Complete {threshold} audio lessons.'
    WHEN 4 THEN 'Maintain a streak for {threshold} days.'
    WHEN 5 THEN 'Learn {threshold} new words.'
    WHEN 6 THEN 'Read {threshold} articles.'
    WHEN 7 THEN 'Add {threshold} friends.'
  END
WHERE id IN (1,2,3,4,5,6,7);

-- Enforce NOT NULL after data is populated
ALTER TABLE badge_category
  MODIFY singular_default_description TEXT NOT NULL,
  MODIFY plural_default_description TEXT NOT NULL;
