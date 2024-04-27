ALTER TABLE
    `zeeguu_test`.`article`
ADD
    COLUMN `img_url_id` INT NULL
AFTER
    `deleted`,
ADD
    UNIQUE INDEX `img_url_id_UNIQUE` (`img_url_id` ASC);

;

ALTER TABLE
    `zeeguu_test`.`article`
ADD
    CONSTRAINT `article_ibfk_5` FOREIGN KEY (`img_url_id`) REFERENCES `zeeguu_test`.`url` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION;
