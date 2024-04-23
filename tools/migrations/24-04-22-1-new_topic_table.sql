CREATE TABLE `zeeguu_test`.`new_topic` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `title` VARCHAR(30) NOT NULL,
    PRIMARY KEY (`id`)
);

# Insert New Topic values into the DB.
INSERT INTO
    `new_topic`
VALUES
    (1, 'Sports'),
    (2, 'Culture & Art'),
    (3, 'Technology & Science'),
    (4, 'Travel & Tourism'),
    (5, 'Health & Society'),
    (6, 'Business'),
    (7, 'Politics'),
    (8, 'Satire');

CREATE TABLE `zeeguu_test`.`new_article_topic_map` (
    `article_id` INT NOT NULL,
    `new_topic_id` INT NOT NULL,
    `origin_type` INT NULL,
    PRIMARY KEY (`article_id`, `new_topic_id`),
    INDEX `new_article_topic_map_ibfk_2_idx` (`new_topic_id` ASC) VISIBLE,
    CONSTRAINT `new_article_topic_map_ibfk_1` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `new_article_topic_map_ibfk_2` FOREIGN KEY (`new_topic_id`) REFERENCES `zeeguu_test`.`new_topic` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);