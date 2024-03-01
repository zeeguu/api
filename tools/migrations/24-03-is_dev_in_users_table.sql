/* Not all devs necessarily will have a 
 Teacher account and vice-versa. 
 Instead, the information will be stored in the user table.
 
 1. Create a new column in user table, is_dev;
 2. Find all the users that are currently devs and set them.
 3. Delete is_dev in the teacher_cohort table.
 */
ALTER TABLE
    `zeeguu_test`.`user`
ADD
    COLUMN `is_dev` TINYINT NULL DEFAULT 0
AFTER
    `cohort_id`;

UPDATE
    `zeeguu_test`.`user`
SET
    is_dev = 1
WHERE
    id in (
        SELECT
            DISTINCT user_id
        FROM
            zeeguu_test.teacher_cohort_map
        WHERE
            is_dev = 1
    )
    /* Tiago's Test user*/
    OR id = 4089;

ALTER TABLE
    `zeeguu_test`.`teacher_cohort_map` DROP COLUMN `is_dev`;