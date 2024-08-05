CREATE TABLE `zeeguu_test`.`article_broken_code_map` (
    `article_id` INT NOT NULL,
    `broken_code` VARCHAR(45) NULL,
    INDEX `article_broken_code_map_ibfk_1_idx` (`article_id` ASC) VISIBLE,
    CONSTRAINT `article_broken_code_map_ibfk_1` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);