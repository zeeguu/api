-- tools/migrations/26-02-20--insert_default_badges.sql

INSERT INTO activity_type (id, metric, name, description, badge_type)
VALUES (1, 'TRANSLATED_WORDS', 'Translated Words', 'Translate {threshold} unique words while reading.', 'COUNTER'),
       (2, 'CORRECT_EXERCISES', 'Correct Exercises', 'Solve {threshold} exercises correctly.', 'COUNTER'),
       (3, 'COMPLETED_AUDIO_LESSONS', 'Completed Audio Lessons', 'Complete {threshold} audio lesson(s).', 'COUNTER'),
       (4, 'STREAK_COUNT', 'Streak Count', 'Maintain a streak for {threshold} days.', 'GAUGE'),
       (5, 'LEARNED_WORDS', 'Learned Words', 'Learn {threshold} new word(s).', 'COUNTER'),
       (6, 'READ_ARTICLES', 'Read Articles', 'Read {threshold} articles.', 'COUNTER'),
       (7, 'NUMBER_OF_FRIENDS', 'Number of Friends', 'Add {threshold} friend(s).', 'GAUGE');

INSERT INTO badge (id, activity_type_id, level, threshold, name, icon_name)
VALUES
    -- Translated Words
    (1, 1, 1, 10, 'Word Explorer', 'translated-words-3.svg'),
    (2, 1, 2, 100, 'Vocabulary Builder', 'translated-words-3.svg'),
    (3, 1, 3, 500, 'Meaning Mapper', 'translated-words-3.svg'),
    (4, 1, 4, 1000, 'Lexicon Navigator', 'translated-words-3.svg'),
    (5, 1, 5, 2500, 'Translation Master', 'translated-words-3.svg'),

    -- Correct Exercises
    (6, 2, 1, 10, 'Exercise Starter', 'correct-exercises-5.svg'),
    (7, 2, 2, 250, 'Practice Builder', 'correct-exercises-5.svg'),
    (8, 2, 3, 1000, 'Practice Grinder', 'correct-exercises-5.svg'),
    (9, 2, 4, 5000, 'Seasoned Solver', 'correct-exercises-5.svg'),
    (10, 2, 5, 20000, 'Exercise Master', 'correct-exercises-5.svg'),

    -- Completed Audio Lessons
    (11, 3, 1, 1, 'Audio Novice', 'completed-audio-lessons-4.svg'),
    (12, 3, 2, 25, 'Sound Seeker', 'completed-audio-lessons-4.svg'),
    (13, 3, 3, 50, 'Accent Explorer', 'completed-audio-lessons-4.svg'),
    (14, 3, 4, 150, 'Fluent Listener', 'completed-audio-lessons-4.svg'),
    (15, 3, 5, 300, 'Audio Virtuoso', 'completed-audio-lessons-4.svg'),

    -- Streak Count
    (16, 4, 1, 7, 'Consistent Starter', 'streak-count-1.svg'),
    (17, 4, 2, 30, 'Streak Builder', 'streak-count-1.svg'),
    (18, 4, 3, 90, 'Dedicated Learner', 'streak-count-1.svg'),
    (19, 4, 4, 180, 'Habitual Learner', 'streak-count-1.svg'),
    (20, 4, 5, 365, 'Streak Master', 'streak-count-1.svg'),

    -- Learned Words
    (21, 5, 1, 1, 'Word Curious', 'learned-words-5.svg'),
    (22, 5, 2, 10, 'Translation Enthusiast', 'learned-words-5.svg'),
    (23, 5, 3, 50, 'Lexical Leader', 'learned-words-5.svg'),
    (24, 5, 4, 250, 'Word Wizard', 'learned-words-5.svg'),
    (25, 5, 5, 750, 'Polyglot Machine', 'learned-words-5.svg'),

    -- Read Articles
    (26, 6, 1, 5, 'Rookie Reader', 'read-articles-3.svg'),
    (27, 6, 2, 25, 'Page Turner', 'read-articles-3.svg'),
    (28, 6, 3, 100, 'Story Seeker', 'read-articles-3.svg'),
    (29, 6, 4, 500, 'Reading Enthusiast', 'read-articles-3.svg'),
    (30, 6, 5, 1000, 'Bookworm', 'read-articles-3.svg'),

    -- Number of Friends
    (31, 7, 1, 1, 'Newcomer', 'number-of-friends-1.svg'),
    (32, 7, 2, 3, 'Connector', 'number-of-friends-1.svg'),
    (33, 7, 3, 5, 'Socializer', 'number-of-friends-1.svg'),
    (34, 7, 4, 7, 'Community Builder', 'number-of-friends-1.svg'),
    (35, 7, 5, 10, 'Leader', 'number-of-friends-1.svg');