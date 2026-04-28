-- Add unachieved descriptions directly on badges.
-- These are used as fallback descriptions before a badge is achieved.
-- Each description already includes the correct threshold value.

ALTER TABLE badge ADD COLUMN unachieved_description TEXT;

UPDATE badge
SET unachieved_description = CASE id
  -- Translated Words
  WHEN 1 THEN 'Translate 10 unique words while reading.'
  WHEN 2 THEN 'Translate 100 unique words while reading.'
  WHEN 3 THEN 'Translate 500 unique words while reading.'
  WHEN 4 THEN 'Translate 1000 unique words while reading.'
  WHEN 5 THEN 'Translate 2500 unique words while reading.'

  -- Correct Exercises
  WHEN 6 THEN 'Solve 10 exercises correctly.'
  WHEN 7 THEN 'Solve 250 exercises correctly.'
  WHEN 8 THEN 'Solve 1000 exercises correctly.'
  WHEN 9 THEN 'Solve 5000 exercises correctly.'
  WHEN 10 THEN 'Solve 20000 exercises correctly.'

  -- Completed Audio Lessons
  WHEN 11 THEN 'Complete an audio lesson.'
  WHEN 12 THEN 'Complete 25 audio lessons.'
  WHEN 13 THEN 'Complete 50 audio lessons.'
  WHEN 14 THEN 'Complete 150 audio lessons.'
  WHEN 15 THEN 'Complete 300 audio lessons.'

  -- Streak Count
  WHEN 16 THEN 'Maintain a streak for 7 days.'
  WHEN 17 THEN 'Maintain a streak for 30 days.'
  WHEN 18 THEN 'Maintain a streak for 90 days.'
  WHEN 19 THEN 'Maintain a streak for 180 days.'
  WHEN 20 THEN 'Maintain a streak for 365 days.'

  -- Learned Words
  WHEN 21 THEN 'Learn a new word.'
  WHEN 22 THEN 'Learn 10 new words.'
  WHEN 23 THEN 'Learn 50 new words.'
  WHEN 24 THEN 'Learn 250 new words.'
  WHEN 25 THEN 'Learn 750 new words.'

  -- Read Articles
  WHEN 26 THEN 'Read 5 articles.'
  WHEN 27 THEN 'Read 25 articles.'
  WHEN 28 THEN 'Read 100 articles.'
  WHEN 29 THEN 'Read 500 articles.'
  WHEN 30 THEN 'Read 1000 articles.'

  -- Number of Friends
  WHEN 31 THEN 'Add a friend.'
  WHEN 32 THEN 'Add 3 friends.'
  WHEN 33 THEN 'Add 5 friends.'
  WHEN 34 THEN 'Add 7 friends.'
  WHEN 35 THEN 'Add 10 friends.'
END
WHERE id BETWEEN 1 AND 35;

-- Enforce NOT NULL after data is populated
ALTER TABLE badge MODIFY unachieved_description TEXT NOT NULL;

ALTER TABLE badge CHANGE description achieved_description TEXT;

-- Update badge descriptions with funnier/playful ones
-- Once a badge is achieved, the corresponding description will be displayed
UPDATE badge
SET
    achieved_description = CASE id
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

-- Enforce NOT NULL after data is populated
ALTER TABLE badge MODIFY achieved_description TEXT NOT NULL;