-- tools/migrations/26-02-28--insert_default_badge.sql

INSERT INTO badge (id, code, name, description)
VALUES
        (1, 'TRANSLATED_WORDS', 'Meaning Builder', 'Translate {target_value} unique words while reading.'),
        (2, 'CORRECT_EXERCISES', 'Practice Builder', 'Solve {target_value} exercises correctly.'),
        (3, 'COMPLETED_AUDIO_LESSONS', 'Sound Scholar', 'Complete {target_value} audio lessons.'),
        (4, 'STREAK_COUNT', 'Consistency Champion', 'Maintain a streak for {target_value} days.'),
        (5, 'LEARNED_WORDS', 'Word Collector', 'Learn {target_value} new words.'),
        (6, 'READ_ARTICLES', 'Active Reader', 'Read {target_value} articles.'),
        (7, 'NUMBER_OF_FRIENDS', 'Influencer', 'Add {target_value} friends.');

INSERT INTO badge_level (id, badge_id, name, level, target_value, icon_name)
VALUES
        -- Translated Words
        (1, 1, '', 1, 10, NULL),
        (2, 1, '', 2, 100, NULL),
        (3, 1, '', 3, 500, NULL),
        (4, 1, '', 4, 1000, NULL),
        (5, 1, '', 5, 2500, NULL),

        -- Correct Exercises
        (6, 2, '', 1, 10, NULL),
        (7, 2, '', 2, 250, NULL),
        (8, 2, '', 3, 1000, NULL),
        (9, 2, '', 4, 5000, NULL),
        (10, 2, '', 5, 20000, NULL),

        -- Completed Audio Lessons
        (11, 3, '', 1, 1, NULL),
        (12, 3, '', 2, 25, NULL),
        (13, 3, '', 3, 50, NULL),
        (14, 3, '', 4, 150, NULL),
        (15, 3, '', 5, 300, NULL),

        -- Streak Count
        (16, 4, '', 1, 7, NULL),
        (17, 4, '', 2, 30, NULL),
        (18, 4, '', 3, 90, NULL),
        (19, 4, '', 4, 180, NULL),
        (20, 4, '', 5, 365, NULL),

        -- Learned Words
        (21, 5, '', 1, 1, NULL),
        (22, 5, '', 2, 10, NULL),
        (23, 5, '', 3, 50, NULL),
        (24, 5, '', 4, 250, NULL),
        (25, 5, '', 5, 750, NULL),

        -- Read Articles
        (26, 6, '', 1, 5, NULL),
        (27, 6, '', 2, 25, NULL),
        (28, 6, '', 3, 100, NULL),
        (29, 6, '', 4, 500, NULL),
        (30, 6, '', 5, 1000, NULL),

        -- Number of Friends
        (31, 7, '', 1, 1, NULL),
        (32, 7, '', 2, 3, NULL),
        (33, 7, '', 3, 5, NULL),
        (34, 7, '', 4, 7, NULL),
        (35, 7, '', 5, 10, NULL);
