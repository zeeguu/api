CREATE TABLE `zeeguu_test`.`article_topic_user_feedback` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `article_id` INT NOT NULL,
    `new_topic_id` INT NOT NULL,
    `user_id` INT NOT NULL,
    `feedback` VARCHAR(50),
    PRIMARY KEY (`id`),
    INDEX `article_topic_user_feedback_ibfk_1_idx` (`article_id` ASC) VISIBLE,
    INDEX `article_topic_user_feedback_ibfk_2_idx` (`new_topic_id` ASC) VISIBLE,
    INDEX `article_topic_user_feedback_ibfk_3_idx` (`user_id` ASC) VISIBLE,
    CONSTRAINT `article_topic_user_feedback_ibfk_1` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `article_topic_user_feedback_ibfk_2` FOREIGN KEY (`new_topic_id`) REFERENCES `zeeguu_test`.`new_topic` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `article_topic_user_feedback_ibfk_3` FOREIGN KEY (`user_id`) REFERENCES `zeeguu_test`.`user` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);