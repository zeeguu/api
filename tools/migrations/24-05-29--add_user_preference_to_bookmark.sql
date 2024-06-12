ALTER TABLE
    `zeeguu_test`.`bookmark`
ADD
    COLUMN `user_preference` TINYINT NULL DEFAULT 0
AFTER
    `learning_cycle`;

UPDATE
    `zeeguu_test`.`bookmark`
SET
    `user_preference` = `starred`
WHERE
    starred is not NULL;