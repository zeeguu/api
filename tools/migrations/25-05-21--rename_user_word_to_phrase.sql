alter table user_word RENAME TO phrase;

ALTER TABLE phrase
    DROP INDEX unique_word_language;


ALTER TABLE phrase
    CHANGE COLUMN word content VARCHAR(255)
        CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci;
