CREATE TABLE `zeeguu_test`.`url_keyword` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `language_id` INT NULL,
    `new_topic_id` INT NULL,
    `keyword` VARCHAR(50) NULL,
    `type` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `url_keyword_ibfk_1_idx` (`language_id` ASC) VISIBLE,
    INDEX `url_keyword_ibfk_2_idx` (`new_topic_id` ASC) VISIBLE,
    CONSTRAINT `url_keyword_ibfk_1` FOREIGN KEY (`language_id`) REFERENCES `zeeguu_test`.`language` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `url_keyword_ibfk_2` FOREIGN KEY (`new_topic_id`) REFERENCES `zeeguu_test`.`new_topic` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_url_keyword_map` (
    `article_id` INT NOT NULL,
    `url_keyword_id` INT NOT NULL,
    `rank` INT NULL,
    PRIMARY KEY (`article_id`, `url_keyword_id`),
    INDEX `article_url_keyword_map_ibfk_2_idx` (`url_keyword_id` ASC) VISIBLE,
    CONSTRAINT `article_url_keyword_map_ibfk_1` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `article_url_keyword_map_ibfk_2` FOREIGN KEY (`url_keyword_id`) REFERENCES `zeeguu_test`.`url_keyword` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);