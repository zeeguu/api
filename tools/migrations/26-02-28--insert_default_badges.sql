-- tools/migrations/26-02-28--insert_default_badges.sql

INSERT INTO activity_type (id, metric_key, name, description, is_accumulative)
VALUES
        (1, 'TRANSLATED_WORDS',     'Lexical Leader', 'Translate {target_value} unique words while reading.', TRUE),
        (2, 'CORRECT_EXERCISES',    'Practice Builder', 'Solve {target_value} exercises correctly.',          TRUE),
        (3, 'COMPLETED_AUDIO_LESSONS', 'Sound Scholar', 'Complete {target_value} audio lesson(s).',          TRUE),
        (4, 'STREAK_COUNT',         'Habit Hero', 'Maintain a streak for {target_value} days.',               TRUE),
        (5, 'LEARNED_WORDS',        'Word Collector', 'Learn {target_value} new word(s).',                    TRUE),
        (6, 'READ_ARTICLES',        'Active Reader', 'Read {target_value} articles.',                         TRUE),
        (7, 'NUMBER_OF_FRIENDS',    'Influencer', 'Add {target_value} friend(s).',                            TRUE);

INSERT INTO badge (id, activity_type_id, level, threshold, name, icon_name)
VALUES
        -- Translated Words
        (1,  1, 1, 10,    NULL, 'translated-words-3.svg'),
        (2,  1, 2, 100,   NULL, 'translated-words-3.svg'),
        (3,  1, 3, 500,   NULL, 'translated-words-3.svg'),
        (4,  1, 4, 1000,  NULL, 'translated-words-3.svg'),
        (5,  1, 5, 2500,  NULL, 'translated-words-3.svg'),

        -- Correct Exercises
        (6,  2, 1, 10,    NULL, 'correct-exercises-5.svg'),
        (7,  2, 2, 250,   NULL, 'correct-exercises-5.svg'),
        (8,  2, 3, 1000,  NULL, 'correct-exercises-5.svg'),
        (9,  2, 4, 5000,  NULL, 'correct-exercises-5.svg'),
        (10, 2, 5, 20000, NULL, 'correct-exercises-5.svg'),

        -- Completed Audio Lessons
        (11, 3, 1, 1,   NULL, 'completed-audio-lessons-4.svg'),
        (12, 3, 2, 25,  NULL, 'completed-audio-lessons-4.svg'),
        (13, 3, 3, 50,  NULL, 'completed-audio-lessons-4.svg'),
        (14, 3, 4, 150, NULL, 'completed-audio-lessons-4.svg'),
        (15, 3, 5, 300, NULL, 'completed-audio-lessons-4.svg'),

        -- Streak Count
        (16, 4, 1, 7,   NULL, 'streak-count-1.svg'),
        (17, 4, 2, 30,  NULL, 'streak-count-1.svg'),
        (18, 4, 3, 90,  NULL, 'streak-count-1.svg'),
        (19, 4, 4, 180, NULL, 'streak-count-1.svg'),
        (20, 4, 5, 365, NULL, 'streak-count-1.svg'),

        -- Learned Words
        (21, 5, 1, 1,   NULL, 'learned-words-5.svg'),
        (22, 5, 2, 10,  NULL, 'learned-words-5.svg'),
        (23, 5, 3, 50,  NULL, 'learned-words-5.svg'),
        (24, 5, 4, 250, NULL, 'learned-words-5.svg'),
        (25, 5, 5, 750, NULL, 'learned-words-5.svg'),

        -- Read Articles
        (26, 6, 1, 5,    NULL, 'read-articles-3.svg'),
        (27, 6, 2, 25,   NULL, 'read-articles-3.svg'),
        (28, 6, 3, 100,  NULL, 'read-articles-3.svg'),
        (29, 6, 4, 500,  NULL, 'read-articles-3.svg'),
        (30, 6, 5, 1000, NULL, 'read-articles-3.svg'),

        -- Number of Friends
        (31, 7, 1, 1,  NULL, 'number-of-friends-1.svg'),
        (32, 7, 2, 3,  NULL, 'number-of-friends-1.svg'),
        (33, 7, 3, 5,  NULL, 'number-of-friends-1.svg'),
        (34, 7, 4, 7,  NULL, 'number-of-friends-1.svg'),
        (35, 7, 5, 10, NULL, 'number-of-friends-1.svg');
