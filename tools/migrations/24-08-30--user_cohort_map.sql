CREATE TABLE `zeeguu_test`.`user_cohort_map` (
    `user_id` INT NOT NULL,
    `cohort_id` INT NOT NULL,
    PRIMARY KEY (`user_id`, `cohort_id`),
    INDEX `cohort_id_ibfk_1_idx` (`user_id` ASC) VISIBLE,
    CONSTRAINT `user_cohort_map_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `zeeguu_test`.`user` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `user_cohort_map_ibfk_2` FOREIGN KEY (`cohort_id`) REFERENCES `zeeguu_test`.`cohort` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

INSERT INTO
    user_cohort_map (user_id, cohort_id)
SELECT
    id,
    cohort_id
from
    user
WHERE
    cohort_id is not null;

ALTER TABLE
    `zeeguu_test`.`user` DROP FOREIGN KEY `user_ibfk_3`;

ALTER TABLE
    `zeeguu_test`.`user` DROP COLUMN `cohort_id`,
    DROP INDEX `cohort_id`;

;