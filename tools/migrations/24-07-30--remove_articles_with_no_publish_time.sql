DELETE FROM
    `zeeguu_test`.`user_article`
WHERE
    article_id in (
        select
            id
        from
            article a
        where
            a.published_time is null
    );

DELETE FROM
    `zeeguu_test`.`user_reading_session`
WHERE
    article_id in (
        select
            id
        from
            article a
        where
            a.published_time is null
    );

DELETE FROM
    `zeeguu_test`.`personal_copy`
WHERE
    article_id in (
        select
            id
        from
            article a
        where
            a.published_time is null
    );

DELETE FROM
    `zeeguu_test`.`article`
WHERE
    published_time is null;

ALTER TABLE
    `zeeguu_test`.`article` CHANGE COLUMN `published_time` `published_time` DATETIME NOT NULL;