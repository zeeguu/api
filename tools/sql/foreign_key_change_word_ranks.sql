UPDATE exercise_outcome
SET outcome='Show solution'
WHERE outcome='Do not know';

UPDATE exercise_outcome
SET outcome='Too easy'
WHERE outcome='I know';


DROP TABLE IF EXISTS words;

ALTER TABLE word_ranks
RENAME TO word_rank;

ALTER TABLE user_words
RENAME TO user_word;

