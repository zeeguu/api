CREATE TABLE `zeeguu_test`.`user_onboarding_message` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NULL,
    `onboarding_message_id` INT NULL,
    `message_shown_time` DATETIME NULL,
    `message_click_time` DATETIME NULL,
    PRIMARY KEY (`id`),
    INDEX `user_onboarding_message_ibfk_1_idx` (`user_id` ASC),
    INDEX `user_onboarding_message_ibfk_2_idx` (`onboarding_message_id` ASC),
    CONSTRAINT `user_onboarding_message_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `zeeguu_test`.`user` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `user_onboarding_message_ibfk_2` FOREIGN KEY (`onboarding_message_id`) REFERENCES `zeeguu_test`.`onboarding_message` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);
