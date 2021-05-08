-- rename  purposes of user word and ranked word tables. Rename also columns of exercise outcome

UPDATE exercise_outcome
SET outcome='Show solution'
WHERE outcome='Do not know';

UPDATE exercise_outcome
SET outcome='Too easy'
WHERE outcome='I know';


DROP TABLE IF EXISTS words;

ALTER TABLE word_ranks
RENAME TO ranked_word;

ALTER TABLE user_words
RENAME TO user_word;

