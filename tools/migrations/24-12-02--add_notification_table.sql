CREATE TABLE `zeeguu_test`.`notification` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `type` VARCHAR(45) NULL,
    PRIMARY KEY (`id`)
);

INSERT INTO
    `notification`
VALUES
    (1, 'EXERCISE_AVAILABLE'),
    (2, 'NEW_ARTICLE_AVAILABLE'),
    (3, 'DAILY_LOGIN');