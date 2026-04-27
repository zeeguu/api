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



-- Update badge descriptions with funnier/playful ones
-- Once a badge is achieved, the corresponding description from here will be displayed
UPDATE badge
SET
    description = CASE id
      -- Translated Words
      WHEN 1 THEN '10 words translated. Each tap, a tiny ''aha!''.'
      WHEN 2 THEN '100 words cracked open. Your future self is already impressed.'
      WHEN 3 THEN '500 words decoded. The dictionary is starting to sweat.'
      WHEN 4 THEN '1000 words in. At this point, you''re arguing with the dictionary.'
      WHEN 5 THEN '2500 words translated. The dictionary now checks with you.'

      -- Correct Exercises
      WHEN 6 THEN '10 exercises down. The warm-up is officially over.'
      WHEN 7 THEN '250 right answers. This is no longer a coincidence.'
      WHEN 8 THEN '1000 exercises. Muscle memory, but for grammar.'
      WHEN 9 THEN '5000 correct answers. Mistakes are now a distant memory.'
      WHEN 10 THEN '20000 exercises solved. At this point, you''re training the exercises.'

      -- Completed Audio Lessons
      WHEN 11 THEN 'Your first audio lesson. The voice in your headphones is your new tutor.'
      WHEN 12 THEN '25 lessons in. You''re starting to catch words without subtitles.'
      WHEN 13 THEN '50 lessons. Your ear is tuning in to a whole new frequency.'
      WHEN 14 THEN '150 lessons deep. You hear meaning where others hear noise.'
      WHEN 15 THEN '300 lessons done. You could probably subtitle real life.'

      -- Streak Count
      WHEN 16 THEN 'A full week, no days off. That''s a habit forming.'
      WHEN 17 THEN '30 days in a row. Not even the weekend could stop you.'
      WHEN 18 THEN '90 days straight. This is no longer practice, it''s a lifestyle.'
      WHEN 19 THEN '180 days straight. Missing a day would feel illegal.'
      WHEN 20 THEN 'A full year streak. This is no longer a habit, it''s a personality.'

      -- Learned Words
      WHEN 21 THEN 'Your first word, learned and locked in. Many more where that came from.'
      WHEN 22 THEN '10 words mastered. Your brain just got a little more multilingual.'
      WHEN 23 THEN '50 words that won''t slip away. The mental dictionary is filling up.'
      WHEN 24 THEN '250 words learned. Your brain is officially multilingual real estate.'
      WHEN 25 THEN '750 words mastered. You don''t just recognize them, you use them.'

      -- Read Articles
      WHEN 26 THEN '5 articles finished. The news just got more interesting.'
      WHEN 27 THEN '25 articles. You''re not browsing — you''re reading.'
      WHEN 28 THEN '100 articles in. You''ve got opinions now, and they''re in another language.'
      WHEN 29 THEN '500 articles in. You''re moving through texts without slowing down.'
      WHEN 30 THEN '1000 articles read. Reading feels natural now, not like practice.'

      -- Number of Friends
      WHEN 31 THEN 'Your first friend. The journey is better with company.'
      WHEN 32 THEN '3 friends on board. The vibes are starting.'
      WHEN 33 THEN '5 friends learning alongside you. Safety in numbers.'
      WHEN 34 THEN '7 friends. This is starting to feel like a solid circle.'
      WHEN 35 THEN '10 friends. You''ve built a small community.'
    END
WHERE ID BETWEEN 1 AND 35;