CREATE TABLE `zeeguu_test`.`new_topic_filter` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NULL DEFAULT NULL,
    `new_topic_id` INT NULL DEFAULT NULL,
    PRIMARY KEY (`id`),
    INDEX `new_topic_filter_ibfk_1_idx` (`user_id` ASC) VISIBLE,
    INDEX `new_topic_filter_ibfk_2_idx` (`new_topic_id` ASC) VISIBLE,
    CONSTRAINT `new_topic_filter_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `zeeguu_test`.`user` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT `new_topic_filter_ibfk_2` FOREIGN KEY (`new_topic_id`) REFERENCES `zeeguu_test`.`new_topic` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
);