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
    (1, 1, 1, 10, 'Word Explorer', 'Ten words cracked open. Each tap, a tiny ''aha!''.', 'translated-words.svg'),
    (2, 1, 2, 100, 'Vocabulary Builder', 'A hundred words logged. Your future self is already impressed.', 'translated-words.svg'),
    (3, 1, 3, 500, 'Meaning Mapper', 'Five hundred words decoded. The dictionary is starting to sweat.', 'translated-words.svg'),
    (4, 1, 4, 1000, 'Lexicon Navigator', 'Translate {threshold} unique words while reading.', 'translated-words.svg'),
    (5, 1, 5, 2500, 'Translation Master', 'Translate {threshold} unique words while reading.', 'translated-words.svg'),

    -- Correct Exercises
    (6, 2, 1, 10, 'Exercise Starter', 'Ten exercises down. The warm-up is officially over.', 'correct-exercises.svg'),
    (7, 2, 2, 250, 'Practice Builder', '250 right answers. This is no longer a coincidence.', 'correct-exercises.svg'),
    (8, 2, 3, 1000, 'Practice Grinder', 'A thousand correct exercises. Muscle memory, but for grammar.', 'correct-exercises.svg'),
    (9, 2, 4, 5000, 'Seasoned Solver', 'Solve {threshold} exercises correctly.', 'correct-exercises.svg'),
    (10, 2, 5, 20000, 'Exercise Master', 'Solve {threshold} exercises correctly.', 'correct-exercises.svg'),

    -- Completed Audio Lessons
    (11, 3, 1, 1, 'Audio Novice', 'Your first audio lesson. The voice in your headphones is your new tutor.', 'completed-audio-lessons.svg'),
    (12, 3, 2, 25, 'Sound Seeker', 'Twenty-five lessons in. You''re starting to catch words without subtitles.', 'completed-audio-lessons.svg'),
    (13, 3, 3, 50, 'Accent Explorer', 'Fifty lessons. Your ear is tuning in to a whole new frequency.', 'completed-audio-lessons.svg'),
    (14, 3, 4, 150, 'Fluent Listener', 'Complete {threshold} audio lessons.', 'completed-audio-lessons.svg'),
    (15, 3, 5, 300, 'Audio Virtuoso', 'Complete {threshold} audio lessons.', 'completed-audio-lessons.svg'),

    -- Streak Count
    (16, 4, 1, 7, 'Consistent Starter', 'A full week, no days off. That''s a habit forming.', 'streak-days.svg'),
    (17, 4, 2, 30, 'Streak Builder', 'Thirty days in a row. Not even the weekend could stop you.', 'streak-days.svg'),
    (18, 4, 3, 90, 'Dedicated Learner', 'Ninety days straight. This is no longer practice — it''s a lifestyle.', 'streak-days.svg'),
    (19, 4, 4, 180, 'Habitual Learner', 'Maintain a streak for {threshold} days.', 'streak-days.svg'),
    (20, 4, 5, 365, 'Streak Master', 'Maintain a streak for {threshold} days.', 'streak-days.svg'),

    -- Learned Words
    (21, 5, 1, 1, 'Word Curious', 'Your first word, learned and locked in. Many more where that came from.', 'learned-words.svg'),
    (22, 5, 2, 10, 'Translation Enthusiast', 'Ten words mastered. Your brain just got a little more multilingual.', 'learned-words.svg'),
    (23, 5, 3, 50, 'Lexical Leader', 'Fifty words that won''t slip away. The mental dictionary is filling up.', 'learned-words.svg'),
    (24, 5, 4, 250, 'Word Wizard', 'Learn {threshold} new words.', 'learned-words.svg'),
    (25, 5, 5, 750, 'Polyglot Machine', 'Learn {threshold} new words.', 'learned-words.svg'),

    -- Read Articles
    (26, 6, 1, 5, 'Rookie Reader', 'Five articles finished. The news just got more interesting.', 'read-articles.svg'),
    (27, 6, 2, 25, 'Page Turner', 'Twenty-five articles. You''re not browsing — you''re reading.', 'read-articles.svg'),
    (28, 6, 3, 100, 'Story Seeker', 'A hundred articles in. You''ve got opinions now, and they''re in another language.', 'read-articles.svg'),
    (29, 6, 4, 500, 'Reading Enthusiast', 'Read {threshold} articles.', 'read-articles.svg'),
    (30, 6, 5, 1000, 'Bookworm', 'Read {threshold} articles.', 'read-articles.svg'),

    -- Number of Friends
    (31, 7, 1, 1, 'Newcomer', 'Your first friend. The journey is better with company.', 'friends.svg'),
    (32, 7, 2, 3, 'Connector', 'Three friends on board. The vibes are starting.', 'friends.svg'),
    (33, 7, 3, 5, 'Socializer', 'Five friends learning alongside you. Safety in numbers.', 'friends.svg'),
    (34, 7, 4, 7, 'Community Builder', 'Add {threshold} friends.', 'friends.svg'),
    (35, 7, 5, 10, 'Leader', 'Add {threshold} friends.', 'friends.svg');
