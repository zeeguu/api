-- tools/migrations/26-02-19-b--insert_default_badges.sql

INSERT INTO badge_category (id, metric, name, award_mechanism)
VALUES (1, 'TRANSLATED_WORDS', 'Translated Words', 'COUNTER'),
       (2, 'CORRECT_EXERCISES', 'Correct Exercises', 'COUNTER'),
       (3, 'COMPLETED_AUDIO_LESSONS', 'Completed Audio Lessons', 'COUNTER'),
       (4, 'STREAK_DAYS', 'Streak Days', 'GAUGE'),
       (5, 'LEARNED_WORDS', 'Learned Words', 'COUNTER'),
       (6, 'READ_ARTICLES', 'Read Articles', 'COUNTER'),
       (7, 'FRIENDS', 'Friends', 'GAUGE');

INSERT INTO badge (id, badge_category_id, level, threshold, name, description, icon_name)
VALUES
    -- Translated Words
    (1, 1, 1, 10, 'Word Explorer', 'Translate {threshold} unique words while reading.', 'translated-words.svg'),
    (2, 1, 2, 100, 'Vocabulary Builder', 'Translate {threshold} unique words while reading.', 'translated-words.svg'),
    (3, 1, 3, 500, 'Meaning Mapper', 'Translate {threshold} unique words while reading.', 'translated-words.svg'),
    (4, 1, 4, 1000, 'Lexicon Navigator', 'Translate {threshold} unique words while reading.', 'translated-words.svg'),
    (5, 1, 5, 2500, 'Translation Master', 'Translate {threshold} unique words while reading.', 'translated-words.svg'),

    -- Correct Exercises
    (6, 2, 1, 10, 'Exercise Starter', 'Solve {threshold} exercises correctly.', 'correct-exercises.svg'),
    (7, 2, 2, 250, 'Practice Builder', 'Solve {threshold} exercises correctly.', 'correct-exercises.svg'),
    (8, 2, 3, 1000, 'Practice Grinder', 'Solve {threshold} exercises correctly.', 'correct-exercises.svg'),
    (9, 2, 4, 5000, 'Seasoned Solver', 'Solve {threshold} exercises correctly.', 'correct-exercises.svg'),
    (10, 2, 5, 20000, 'Exercise Master', 'Solve {threshold} exercises correctly.', 'correct-exercises.svg'),

    -- Completed Audio Lessons
    (11, 3, 1, 1, 'Audio Novice', 'Complete your first audio lesson.', 'completed-audio-lessons.svg'),
    (12, 3, 2, 25, 'Sound Seeker', 'Complete {threshold} audio lessons.', 'completed-audio-lessons.svg'),
    (13, 3, 3, 50, 'Accent Explorer', 'Complete {threshold} audio lessons.', 'completed-audio-lessons.svg'),
    (14, 3, 4, 150, 'Fluent Listener', 'Complete {threshold} audio lessons.', 'completed-audio-lessons.svg'),
    (15, 3, 5, 300, 'Audio Virtuoso', 'Complete {threshold} audio lessons.', 'completed-audio-lessons.svg'),

    -- Streak Count
    (16, 4, 1, 7, 'Consistent Starter', 'Maintain a streak for {threshold} days.', 'streak-days.svg'),
    (17, 4, 2, 30, 'Streak Builder', 'Maintain a streak for {threshold} days.', 'streak-days.svg'),
    (18, 4, 3, 90, 'Dedicated Learner', 'Maintain a streak for {threshold} days.', 'streak-days.svg'),
    (19, 4, 4, 180, 'Habitual Learner', 'Maintain a streak for {threshold} days.', 'streak-days.svg'),
    (20, 4, 5, 365, 'Streak Master', 'Maintain a streak for {threshold} days.', 'streak-days.svg'),

    -- Learned Words
    (21, 5, 1, 1, 'Word Curious', 'Learn a new word.', 'learned-words.svg'),
    (22, 5, 2, 10, 'Translation Enthusiast', 'Learn {threshold} new words.', 'learned-words.svg'),
    (23, 5, 3, 50, 'Lexical Leader', 'Learn {threshold} new words.', 'learned-words.svg'),
    (24, 5, 4, 250, 'Word Wizard', 'Learn {threshold} new words.', 'learned-words.svg'),
    (25, 5, 5, 750, 'Polyglot Machine', 'Learn {threshold} new words.', 'learned-words.svg'),

    -- Read Articles
    (26, 6, 1, 5, 'Rookie Reader', 'Read {threshold} articles.', 'read-articles.svg'),
    (27, 6, 2, 25, 'Page Turner', 'Read {threshold} articles.', 'read-articles.svg'),
    (28, 6, 3, 100, 'Story Seeker', 'Read {threshold} articles.', 'read-articles.svg'),
    (29, 6, 4, 500, 'Reading Enthusiast', 'Read {threshold} articles.', 'read-articles.svg'),
    (30, 6, 5, 1000, 'Bookworm', 'Read {threshold} articles.', 'read-articles.svg'),

    -- Number of Friends
    (31, 7, 1, 1, 'Newcomer', 'Add a friend.', 'friends.svg'),
    (32, 7, 2, 3, 'Connector', 'Add {threshold} friends.', 'friends.svg'),
    (33, 7, 3, 5, 'Socializer', 'Add {threshold} friends.', 'friends.svg'),
    (34, 7, 4, 7, 'Community Builder', 'Add {threshold} friends.', 'friends.svg'),
    (35, 7, 5, 10, 'Leader', 'Add {threshold} friends.', 'friends.svg');
