/*
 Renaming the new topics tables, to not have new.
 */
ALTER TABLE
    `zeeguu_test`.`new_topic` RENAME TO `zeeguu_test`.`topic`;

/* new_topic_filter -> topic_filter */
ALTER TABLE
    `zeeguu_test`.`new_topic_filter` DROP FOREIGN KEY `new_topic_filter_ibfk_2`;

ALTER TABLE
    `zeeguu_test`.`new_topic_filter` CHANGE COLUMN `new_topic_id` `topic_id` INT NULL DEFAULT NULL,
    RENAME TO `zeeguu_test`.`topic_filter`;

ALTER TABLE
    `zeeguu_test`.`new_topic_filter`
ADD
    CONSTRAINT `topic_filter_ibfk_2` FOREIGN KEY (`topic_id`) REFERENCES `zeeguu_test`.`topic` (`id`);

ALTER TABLE
    `zeeguu_test`.`new_topic_filter` RENAME TO `zeeguu_test`.`topic_filter`;

/* new_topic_subscription -> topic_subscription */
ALTER TABLE
    `zeeguu_test`.`new_topic_subscription` DROP FOREIGN KEY `new_topic_subscription_ibfk_2`;

ALTER TABLE
    `zeeguu_test`.`new_topic_subscription` CHANGE COLUMN `new_topic_id` `topic_id` INT NULL DEFAULT NULL;

ALTER TABLE
    `zeeguu_test`.`new_topic_subscription`
ADD
    CONSTRAINT `topic_subscription_ibfk_2` FOREIGN KEY (`topic_id`) REFERENCES `zeeguu_test`.`topic` (`id`);

ALTER TABLE
    `zeeguu_test`.`new_topic_subscription` RENAME TO `zeeguu_test`.`topic_subscription`;

/* new_topic_user_feedback -> topic_user_feedback */
ALTER TABLE
    `zeeguu_test`.`new_topic_user_feedback` DROP FOREIGN KEY `new_topic_user_feedback_ibfk_3`;

ALTER TABLE
    `zeeguu_test`.`new_topic_user_feedback` CHANGE COLUMN `new_topic_id` `topic_id` INT NULL DEFAULT NULL;

ALTER TABLE
    `zeeguu_test`.`new_topic_user_feedback`
ADD
    CONSTRAINT `topic_user_feedback_ibfk_3` FOREIGN KEY (`topic_id`) REFERENCES `zeeguu_test`.`topic` (`id`);

ALTER TABLE
    `zeeguu_test`.`new_topic_user_feedback` RENAME TO `zeeguu_test`.`topic_user_feedback`;

/* new_article_topic_map -> article_topic_map */
ALTER TABLE
    `zeeguu_test`.`new_article_topic_map` DROP FOREIGN KEY `new_article_topic_map_ibfk_2`;

ALTER TABLE
    `zeeguu_test`.`new_article_topic_map` CHANGE COLUMN `new_topic_id` `topic_id` INT NOT NULL;

ALTER TABLE
    `zeeguu_test`.`new_article_topic_map`
ADD
    CONSTRAINT `article_topic_map_ibfk_2` FOREIGN KEY (`topic_id`) REFERENCES `zeeguu_test`.`topic` (`id`);

ALTER TABLE
    `zeeguu_test`.`new_article_topic_map` RENAME TO `zeeguu_test`.`article_topic_map`;

/*article_topic_user_feedback, update reference column name*/
ALTER TABLE
    `zeeguu_test`.`article_topic_user_feedback` DROP FOREIGN KEY `article_topic_user_feedback_ibfk_3`;

ALTER TABLE
    `zeeguu_test`.`article_topic_user_feedback` CHANGE COLUMN `new_topic_id` `topic_id` INT NULL DEFAULT NULL;

ALTER TABLE
    `zeeguu_test`.`article_topic_user_feedback`
ADD
    CONSTRAINT `article_topic_user_feedback_ibfk_3` FOREIGN KEY (`topic_id`) REFERENCES `zeeguu_test`.`topic` (`id`);

/* url_keyword, update reference column name */
ALTER TABLE
    `zeeguu_test`.`url_keyword` DROP FOREIGN KEY `url_keyword_ibfk_2`;

ALTER TABLE
    `zeeguu_test`.`url_keyword` CHANGE COLUMN `new_topic_id` `topic_id` INT NULL DEFAULT NULL;

ALTER TABLE
    `zeeguu_test`.`url_keyword`
ADD
    CONSTRAINT `url_keyword_ibfk_2` FOREIGN KEY (`topic_id`) REFERENCES `zeeguu_test`.`topic` (`id`);