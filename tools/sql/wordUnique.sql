-- This script is executed to make word and language_id column to unique in ranked_word and user_word

ALTER TABLE ranked_word
DROP INDEX uc_wordID,
ADD CONSTRAINT wr_word UNIQUE (word,language_id);

ALTER TABLE user_word
DROP INDEX uc_wordID,
ADD CONSTRAINT uw_word UNIQUE (word,language_id)