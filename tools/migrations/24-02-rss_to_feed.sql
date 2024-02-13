/* Update the table to be feed rather than rss_feed.
  Add the column feed_type which should match the handlers defined in 
    zeeguu/core/feedhandler.py
*/
ALTER TABLE `zeeguu_test`.`rss_feed` RENAME TO  `zeeguu_test`.`feed`;
ALTER TABLE `zeeguu_test`.`feed` ADD COLUMN `feed_type` INT NOT NULL DEFAULT 0 AFTER `deactivated`;

/* Update the article table to match the updated feed table.
*/
ALTER TABLE `zeeguu_test`.`article` DROP FOREIGN KEY `article_ibfk_1`;
ALTER TABLE `zeeguu_test`.`article` CHANGE COLUMN `rss_feed_id` `feed_id` INT NULL DEFAULT NULL ;
ALTER TABLE `zeeguu_test`.`article` 
ADD CONSTRAINT `article_ibfk_1`
  FOREIGN KEY (`feed_id`)
  REFERENCES `zeeguu_test`.`feed` (`id`);
