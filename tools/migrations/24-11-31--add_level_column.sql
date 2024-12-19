/* 
 Create a new level column in bookmark table 
 to keep track of the current learning level of the bookmark.
 */
ALTER TABLE
    `bookmark`
ADD
    COLUMN `level` TINYINT NOT NULL DEFAULT 0
AFTER
    `learning_cycle`;