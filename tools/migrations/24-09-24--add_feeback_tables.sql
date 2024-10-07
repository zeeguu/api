CREATE TABLE `zeeguu_test`.`feedback_component` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `component_type` VARCHAR(45) NOT NULL,
    PRIMARY KEY (`id`)
);

INSERT INTO
    `zeeguu_test`.`feedback_component` (`component_type`)
VALUES
    ('Article Reader');

INSERT INTO
    `zeeguu_test`.`feedback_component` (`component_type`)
VALUES
    ('Article Recommendations');

INSERT INTO
    `zeeguu_test`.`feedback_component` (`component_type`)
VALUES
    ('Translation');

INSERT INTO
    `zeeguu_test`.`feedback_component` (`component_type`)
VALUES
    ('Sound');

INSERT INTO
    `zeeguu_test`.`feedback_component` (`component_type`)
VALUES
    ('Exercises');

INSERT INTO
    `zeeguu_test`.`feedback_component` (`component_type`)
VALUES
    ('Extension');

INSERT INTO
    `zeeguu_test`.`feedback_component` (`component_type`)
VALUES
    ('Other');

CREATE TABLE `zeeguu_test`.`user_feedback` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `feedback_component_id` INT NOT NULL,
    `message` VARCHAR(512) NULL,
    `report_time` DATETIME NULL,
    `url_id` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `user_feedback_ibfk_1_idx` (`user_id` ASC),
    INDEX `user_feedback_ibfk_2_idx` (`feedback_component_id` ASC),
    INDEX `user_feedback_ibfk_2_idx1` (`url_id` ASC),
    CONSTRAINT `user_feedback_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `zeeguu_test`.`user` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `user_feedback_ibfk_2` FOREIGN KEY (`feedback_component_id`) REFERENCES `zeeguu_test`.`feedback_component` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `user_feedback_ibfk_3` FOREIGN KEY (`url_id`) REFERENCES `zeeguu_test`.`url` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);