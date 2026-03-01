-- tools/migrations/26-02-28--insert_default_badge.sql

INSERT INTO badge (id, code, name, description, is_hidden)
VALUES
        (1, 'TRANSLATED_WORDS', 'Meaning Builder', 'Translate {target_value} words while reading.', FALSE),
        (2, 'CORRECT_EXERCISES', 'Practice Builder', 'Solve {target_value} exercises correctly.', FALSE),
        (3, 'COMPLETED_AUDIO_LESSONS', 'Sound Scholar', 'Complete {target_value} audio lessons.', FALSE),
        (4, 'STREAK_COUNT', 'Consistency Champion', 'Maintain your streak for {target_value} days.', FALSE),
        (5, 'LEARNED_WORDS', 'Word Collector', 'Learn {target_value} new words.', FALSE),
        (6, 'READ_ARTICLES', 'Active Reader', 'Read {target_value} articles.', FALSE);

INSERT INTO badge_level (id, badge_id, name, level, target_value, icon_url)
VALUES
        -- Translated Words
        (1, 1, '', 1, 50, NULL),
        (2, 1, '', 2, 100, NULL),
        (3, 1, '', 3, 500, NULL),
        (4, 1, '', 4, 1000, NULL),
        (5, 1, '', 5, 2500, NULL),
        (6, 1, '', 6, 5000, NULL),

        -- Correct Exercises
        (7, 2, '', 1, 10, NULL),
        (8, 2, '', 2, 50, NULL),
        (9, 2, '', 3, 200, NULL),
        (10, 2, '', 4, 500, NULL),
        (11, 2, '', 5, 1000, NULL),
        (12, 2, '', 6, 5000, NULL),

        -- Completed Audio Lessons
        (13, 3, '', 1, 1, NULL),
        (14, 3, '', 2, 10, NULL),
        (15, 3, '', 3, 50, NULL),
        (16, 3, '', 4, 100, NULL),
        (17, 3, '', 5, 250, NULL),
        (18, 3, '', 6, 500, NULL),

        -- Streak Count
        (19, 4, '', 1, 7, NULL),
        (20, 4, '', 2, 21, NULL),
        (21, 4, '', 3, 60, NULL),
        (22, 4, '', 4, 180, NULL),
        (23, 4, '', 5, 365, NULL),

        -- Learned Words
        (24, 5, '', 1, 10, NULL),
        (25, 5, '', 2, 50, NULL),
        (26, 5, '', 3, 100, NULL),
        (27, 5, '', 4, 250, NULL),
        (28, 5, '', 5, 500, NULL),
        (29, 5, '', 6, 1000, NULL),

        -- Read Articles
        (30, 6, '', 1, 5, NULL),
        (31, 6, '', 2, 20, NULL),
        (32, 6, '', 3, 50, NULL),
        (33, 6, '', 4, 100, NULL),
        (34, 6, '', 5, 250, NULL),
        (35, 6, '', 6, 500, NULL);
