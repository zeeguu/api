CREATE TABLE `zeeguu_test`.`topic_keyword` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `language_id` INT NULL,
    `new_topic_id` INT NULL,
    `keyword` VARCHAR(50) NULL,
    `type` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `topic_keyword_ibfk_1_idx` (`language_id` ASC) VISIBLE,
    INDEX `topic_keyword_ibfk_2_idx` (`new_topic_id` ASC) VISIBLE,
    CONSTRAINT `topic_keyword_ibfk_1` FOREIGN KEY (`language_id`) REFERENCES `zeeguu_test`.`language` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `topic_keyword_ibfk_2` FOREIGN KEY (`new_topic_id`) REFERENCES `zeeguu_test`.`new_topic` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_topic_keyword_map` (
    `article_id` INT NOT NULL,
    `topic_keyword_id` INT NOT NULL,
    `rank` INT NULL,
    PRIMARY KEY (`article_id`, `topic_keyword_id`),
    INDEX `article_topic_keyword_map_ibfk_2_idx` (`topic_keyword_id` ASC) VISIBLE,
    CONSTRAINT `article_topic_keyword_map_ibfk_1` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `article_topic_keyword_map_ibfk_2` FOREIGN KEY (`topic_keyword_id`) REFERENCES `zeeguu_test`.`topic_keyword` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);