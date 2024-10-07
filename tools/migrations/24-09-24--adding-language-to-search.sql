ALTER TABLE
    `zeeguu_test`.`search`
ADD
    COLUMN `language_id` INT NULL
AFTER
    `id`,
    CHANGE COLUMN `keywords` `keywords` VARCHAR(100) NULL DEFAULT NULL,
ADD
    INDEX `search_ibfk_1_idx` (`language_id` ASC) VISIBLE;

;

ALTER TABLE
    `zeeguu_test`.`search`
ADD
    CONSTRAINT `search_ibfk_1` FOREIGN KEY (`language_id`) REFERENCES `zeeguu_test`.`language` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION;

UPDATE
    `zeeguu_test`.`search` s
    INNER JOIN `zeeguu_test`.`search_subscription` ssub ON s.id = ssub.search_id
    INNER JOIN `zeeguu_test`.`user` u on u.id = ssub.user_id
SET
    s.language_id = u.learned_language_id;

UPDATE
    `zeeguu_test`.`search` s
    INNER JOIN `zeeguu_test`.`search_filter` ssub ON s.id = ssub.search_id
    INNER JOIN `zeeguu_test`.`user` u on u.id = ssub.user_id
SET
    s.language_id = u.learned_language_id;