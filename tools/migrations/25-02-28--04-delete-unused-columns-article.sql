# Delete the videos that are not used anymore
DELETE FROM
    article_difficulty_feedback
where
    article_id in (
        SELECT
            id
        FROM
            zeeguu_test.article
        where
            video = 1
    );

DELETE FROM
    user_reading_session
where
    article_id in (
        SELECT
            id
        FROM
            zeeguu_test.article
        where
            video = 1
    );

DELETE FROM
    user_article
where
    article_id in (
        SELECT
            id
        FROM
            zeeguu_test.article
        where
            video = 1
    );

DELETE from
    article
where
    video = 1;

-- Update the user_activity_data table
-- To have source_id rather than article_id
ALTER TABLE
    `zeeguu_test`.`user_activity_data` DROP COLUMN `has_article_id`;

-- Add source_id collumn and populate it.
ALTER TABLE
    `zeeguu_test`.`user_activity_data`
ADD
    COLUMN `source_id` INT NULL
AFTER
    `article_id`,
ADD
    INDEX `user_activity_data_ibfk_3_idx` (`source_id` ASC) VISIBLE;

;

ALTER TABLE
    `zeeguu_test`.`user_activity_data`
ADD
    CONSTRAINT `user_activity_data_ibfk_3` FOREIGN KEY (`source_id`) REFERENCES `zeeguu_test`.`source` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION;

-- Update source id with articles:
UPDATE
    user_activity_data uad
    JOIN article a ON uad.article_id = a.id
SET
    uad.source_id = a.source_id;

-- SLOW!!!
ALTER TABLE
    `zeeguu_test`.`article` DROP COLUMN `video`,
    DROP COLUMN `fk_difficulty`,
    DROP COLUMN `word_count`,
    DROP COLUMN `content`,
ALTER TABLE
    `zeeguu_test`.`bookmark` DROP FOREIGN KEY `bookmark_ibfk_6`;

ALTER TABLE
    `zeeguu_test`.`bookmark` DROP COLUMN `text_id`,
    DROP INDEX `text_id`;

;

DROP TABLE `zeeguu_test`.`text`;

ALTER TABLE
    `zeeguu_test`.`new_text` RENAME TO `zeeguu_test`.`text`;