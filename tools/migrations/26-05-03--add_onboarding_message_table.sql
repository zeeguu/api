CREATE TABLE `zeeguu_test`.`onboarding_message` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `type` VARCHAR(45) NULL,
    PRIMARY KEY (`id`)
);

INSERT INTO onboarding_message (id, type)
VALUES
    (1, 'TRANSLATE_MSG'),
    (2, 'UNSELECT_MSG'),
    (3, 'REVIEW_WORDS_MSG'),
    (4, 'PRACTICE_MSG'),
    (5, 'DAILY_EXERCISES_MSG'),
    (6, 'WORD_LEVELS_MSG'),
    (7, 'LISTENING_MSG');
