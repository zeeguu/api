ALTER TABLE `zeeguu_test`.`rss_feed` 
DROP FOREIGN KEY `rss_feed_ibfk_2`,
DROP FOREIGN KEY `rss_feed_ibfk_3`,
DROP FOREIGN KEY `rss_feedlanguage_id_fk`;
ALTER TABLE `zeeguu_test`.`rss_feed` 
ADD COLUMN `is_rss` TINYINT NULL DEFAULT 1 AFTER `deactivated`, RENAME TO  `zeeguu_test`.`feed` ;
ALTER TABLE `zeeguu_test`.`feed` 
ADD CONSTRAINT `feed_ibfk_2`
  FOREIGN KEY (`url_id`)
  REFERENCES `zeeguu_test`.`url` (`id`),
ADD CONSTRAINT `feed_ibfk_3`
  FOREIGN KEY (`image_url_id`)
  REFERENCES `zeeguu_test`.`url` (`id`),
ADD CONSTRAINT `feedlanguage_id_fk`
  FOREIGN KEY (`language_id`)
  REFERENCES `zeeguu_test`.`language` (`id`);

ALTER TABLE `zeeguu_test`.`article` 
DROP FOREIGN KEY `article_ibfk_1`;
ALTER TABLE `zeeguu_test`.`article` 
CHANGE COLUMN `rss_feed_id` `feed_id` INT NULL DEFAULT NULL ;
ALTER TABLE `zeeguu_test`.`article` 
ADD CONSTRAINT `article_ibfk_1`
  FOREIGN KEY (`feed_id`)
  REFERENCES `zeeguu_test`.`feed` (`id`);


  CREATE TABLE `zeeguu_test`.`feed_type` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(45) NULL,
  `description` VARCHAR(200) NULL,
  PRIMARY KEY (`id`));
