ALTER TABLE
    `zeeguu_test`.`user_activity_data`
ADD
    COLUMN `source_id` INT NULL
AFTER
    `article_id`,
ADD
    INDEX `user_activity_data_ibfk_3_idx` (`source_id` ASC);

;

ALTER TABLE
    `zeeguu_test`.`user_activity_data`
ADD
    CONSTRAINT `user_activity_data_ibfk_3` FOREIGN KEY (`source_id`) REFERENCES `zeeguu_test`.`source` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION;

UPDATE
    `zeeguu_test`.`user_activity_data` uad
    left join `zeeguu_test`.`article` as a on uad.article_id = a.id
SET
    uad.source_id = a.source_id;