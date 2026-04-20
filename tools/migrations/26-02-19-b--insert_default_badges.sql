-- tools/migrations/26-02-19-b--insert_default_badges.sql

INSERT INTO activity_type (id, metric, name, description, badge_type)
VALUES (1, 'TRANSLATED_WORDS', 'Translated Words', 'Translate {threshold} unique words while reading.', 'COUNTER'),
       (2, 'CORRECT_EXERCISES', 'Correct Exercises', 'Solve {threshold} exercises correctly.', 'COUNTER'),
       (3, 'COMPLETED_AUDIO_LESSONS', 'Completed Audio Lessons', 'Complete {threshold} audio lesson(s).', 'COUNTER'),
       (4, 'STREAK_DAYS', 'Streak Days', 'Maintain a streak for {threshold} days.', 'GAUGE'),
       (5, 'LEARNED_WORDS', 'Learned Words', 'Learn {threshold} new word(s).', 'COUNTER'),
       (6, 'READ_ARTICLES', 'Read Articles', 'Read {threshold} articles.', 'COUNTER'),
       (7, 'FRIENDS', 'Friends', 'Add {threshold} friend(s).', 'GAUGE');

INSERT INTO badge (id, activity_type_id, level, threshold, name, icon_name)
VALUES
    -- Translated Words
    (1, 1, 1, 10, 'Word Explorer', 'translated-words.svg'),
    (2, 1, 2, 100, 'Vocabulary Builder', 'translated-words.svg'),
    (3, 1, 3, 500, 'Meaning Mapper', 'translated-words.svg'),
    (4, 1, 4, 1000, 'Lexicon Navigator', 'translated-words.svg'),
    (5, 1, 5, 2500, 'Translation Master', 'translated-words.svg'),

    -- Correct Exercises
    (6, 2, 1, 10, 'Exercise Starter', 'correct-exercises.svg'),
    (7, 2, 2, 250, 'Practice Builder', 'correct-exercises.svg'),
    (8, 2, 3, 1000, 'Practice Grinder', 'correct-exercises.svg'),
    (9, 2, 4, 5000, 'Seasoned Solver', 'correct-exercises.svg'),
    (10, 2, 5, 20000, 'Exercise Master', 'correct-exercises.svg'),

    -- Completed Audio Lessons
    (11, 3, 1, 1, 'Audio Novice', 'completed-audio-lessons.svg'),
    (12, 3, 2, 25, 'Sound Seeker', 'completed-audio-lessons.svg'),
    (13, 3, 3, 50, 'Accent Explorer', 'completed-audio-lessons.svg'),
    (14, 3, 4, 150, 'Fluent Listener', 'completed-audio-lessons.svg'),
    (15, 3, 5, 300, 'Audio Virtuoso', 'completed-audio-lessons.svg'),

    -- Streak Count
    (16, 4, 1, 7, 'Consistent Starter', 'streak-days.svg'),
    (17, 4, 2, 30, 'Streak Builder', 'streak-days.svg'),
    (18, 4, 3, 90, 'Dedicated Learner', 'streak-days.svg'),
    (19, 4, 4, 180, 'Habitual Learner', 'streak-days.svg'),
    (20, 4, 5, 365, 'Streak Master', 'streak-days.svg'),

    -- Learned Words
    (21, 5, 1, 1, 'Word Curious', 'learned-words.svg'),
    (22, 5, 2, 10, 'Translation Enthusiast', 'learned-words.svg'),
    (23, 5, 3, 50, 'Lexical Leader', 'learned-words.svg'),
    (24, 5, 4, 250, 'Word Wizard', 'learned-words.svg'),
    (25, 5, 5, 750, 'Polyglot Machine', 'learned-words.svg'),

    -- Read Articles
    (26, 6, 1, 5, 'Rookie Reader', 'read-articles.svg'),
    (27, 6, 2, 25, 'Page Turner', 'read-articles.svg'),
    (28, 6, 3, 100, 'Story Seeker', 'read-articles.svg'),
    (29, 6, 4, 500, 'Reading Enthusiast', 'read-articles.svg'),
    (30, 6, 5, 1000, 'Bookworm', 'read-articles.svg'),

    -- Number of Friends
    (31, 7, 1, 1, 'Newcomer', 'friends.svg'),
    (32, 7, 2, 3, 'Connector', 'friends.svg'),
    (33, 7, 3, 5, 'Socializer', 'friends.svg'),
    (34, 7, 4, 7, 'Community Builder', 'friends.svg'),
    (35, 7, 5, 10, 'Leader', 'friends.svg');
