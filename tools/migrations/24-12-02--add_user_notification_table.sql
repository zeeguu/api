CREATE TABLE `zeeguu_test`.`user_notification` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NULL,
    `notification_id` INT NULL,
    `notification_date` DATETIME NULL,
    `notification_click_time` DATETIME NULL,
    PRIMARY KEY (`id`),
    INDEX `user_notification_ibfk_1_idx` (`user_id` ASC),
    INDEX `user_notification_ibfk_2_idx` (`notification_id` ASC),
    CONSTRAINT `user_notification_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `zeeguu_test`.`user` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `user_notification_ibfk_2` FOREIGN KEY (`notification_id`) REFERENCES `zeeguu_test`.`notification` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);