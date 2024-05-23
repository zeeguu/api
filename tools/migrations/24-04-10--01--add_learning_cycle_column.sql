/* 
 Create a new column in bookmark table, learning_cycle, 
 to keep track of the whether the bookmark is in the
 receptive or productive cycle.
 */
ALTER TABLE
    `bookmark`
ADD
    COLUMN `learning_cycle` TINYINT NOT NULL DEFAULT 0
AFTER
    `learned`;