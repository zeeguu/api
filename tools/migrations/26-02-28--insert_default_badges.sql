-- tools/migrations/26-02-28--insert_default_badge.sql

INSERT INTO badge (id, code, name, description)
VALUES
        (1, 'TRANSLATED_WORDS', 'Lexical Leader', 'Translate {target_value} unique words while reading.'),
        (2, 'CORRECT_EXERCISES', 'Practice Builder', 'Solve {target_value} exercises correctly.'),
        (3, 'COMPLETED_AUDIO_LESSONS', 'Sound Scholar', 'Complete {target_value} audio lesson(s).'),
        (4, 'STREAK_COUNT', 'Habit Hero', 'Maintain a streak for {target_value} days.'),
        (5, 'LEARNED_WORDS', 'Word Collector', 'Learn {target_value} new word(s).'),
        (6, 'READ_ARTICLES', 'Active Reader', 'Read {target_value} articles.'),
        (7, 'NUMBER_OF_FRIENDS', 'Influencer', 'Add {target_value} friend(s).');

INSERT INTO badge_level (id, badge_id, level, target_value, icon_name)
VALUES
        -- Translated Words 
        (1, 1, 1, 10, 'translated-words-3.svg'),
        (2, 1, 2, 100, 'translated-words-3.svg'),
        (3, 1, 3, 500, 'translated-words-3.svg'),
        (4, 1, 4, 1000, 'translated-words-3.svg'),
        (5, 1, 5, 2500, 'translated-words-3.svg'),

        -- Correct Exercises
        (6, 2, 1, 10, 'correct-exercises-5.svg'),
        (7, 2, 2, 250, 'correct-exercises-5.svg'),
        (8, 2, 3, 1000, 'correct-exercises-5.svg'),
        (9, 2, 4, 5000, 'correct-exercises-5.svg'),
        (10, 2, 5, 20000, 'correct-exercises-5.svg'),

        -- Completed Audio Lessons
        (11, 3, 1, 1, 'completed-audio-lessons-4.svg'),
        (12, 3, 2, 25, 'completed-audio-lessons-4.svg'),
        (13, 3, 3, 50, 'completed-audio-lessons-4.svg'),
        (14, 3, 4, 150, 'completed-audio-lessons-4.svg'),
        (15, 3, 5, 300, 'completed-audio-lessons-4.svg'),

        -- Streak Count
        (16, 4, 1, 7, 'streak-count-1.svg'),
        (17, 4, 2, 30, 'streak-count-1.svg'),
        (18, 4, 3, 90, 'streak-count-1.svg'),
        (19, 4, 4, 180, 'streak-count-1.svg'),
        (20, 4, 5, 365, 'streak-count-1.svg'),

        -- Learned Words
        (21, 5, 1, 1, 'learned-words-5.svg'),
        (22, 5, 2, 10, 'learned-words-5.svg'),
        (23, 5, 3, 50, 'learned-words-5.svg'),
        (24, 5, 4, 250, 'learned-words-5.svg'),
        (25, 5, 5, 750, 'learned-words-5.svg'),

        -- Read Articles
        (26, 6, 1, 5, 'read-articles-3.svg'),
        (27, 6, 2, 25, 'read-articles-3.svg'),
        (28, 6, 3, 100, 'read-articles-3.svg'),
        (29, 6, 4, 500, 'read-articles-3.svg'),
        (30, 6, 5, 1000, 'read-articles-3.svg'),

        -- Number of Friends
        (31, 7, 1, 1, 'number-of-friends-1.svg'),
        (32, 7, 2, 3, 'number-of-friends-1.svg'),
        (33, 7, 3, 5, 'number-of-friends-1.svg'),
        (34, 7, 4, 7, 'number-of-friends-1.svg'),
        (35, 7, 5, 10, 'number-of-friends-1.svg');
