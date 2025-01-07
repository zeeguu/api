ALTER TABLE
    `zeeguu_test`.`text`
ADD
    COLUMN `content_origin_index` INT NULL
AFTER
    `article_id`;

ALTER TABLE
    `zeeguu_test`.`bookmark`
ADD
    COLUMN `origin_index_at_text` INT NULL
AFTER
    `learned`;