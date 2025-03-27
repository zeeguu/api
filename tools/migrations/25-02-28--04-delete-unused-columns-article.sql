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

-- SLOW!!!
ALTER TABLE
    `zeeguu_test`.`article` DROP COLUMN `video`,
    DROP COLUMN `fk_difficulty`,
    DROP COLUMN `word_count`,
    DROP COLUMN `content`,