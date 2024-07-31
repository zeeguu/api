/*
 adds a receive_email column to the search_subscription table
*/
ALTER TABLE `search_subscription` ADD COLUMN `receive_email` BOOLEAN DEFAULT FALSE;
