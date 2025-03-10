-- Step 1: Create the `yt_channel` table (assuming 'language' table exists)
CREATE TABLE `yt_channel` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `channel_id` varchar(512) NOT NULL,
  `name` varchar(512) DEFAULT NULL,
  `description` mediumtext,
  `views` bigint(20) DEFAULT NULL,
  `subscribers` int(10) unsigned DEFAULT NULL,
  `language_id` int(11) DEFAULT NULL,
  `should_crawl` int(11) DEFAULT NULL,
  `last_crawled` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `yt_channel_unique_channel_id` (`channel_id`),
  KEY `yt_channel_language_FK` (`language_id`),
  CONSTRAINT `yt_channel_language_FK` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`)
);

-- Step 2: Create the `video` table (assuming `yt_channel` table exists)
CREATE TABLE `video` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `video_id` varchar(512) NOT NULL,
  `title` varchar(512) NULL,
  `description` mediumtext,
  `published_at` datetime DEFAULT NULL,
  `channel_id` int(11) DEFAULT NULL,
  `thumbnail_url` varchar(512) DEFAULT NULL,
  `tags` mediumtext,
  `duration` int(11) DEFAULT NULL,
  `language_id` int(11) DEFAULT NULL,
  `vtt` mediumtext,
  `plain_text` mediumtext,
  PRIMARY KEY (`id`),
  UNIQUE KEY `video_unique_video_id` (`video_id`),
  KEY `video_language_FK` (`language_id`),
  KEY `video_yt_channel_FK` (`channel_id`),
  CONSTRAINT `video_language_FK` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`),
  CONSTRAINT `video_yt_channel_FK` FOREIGN KEY (`channel_id`) REFERENCES `yt_channel` (`id`)
);

-- Step 3: Create the `caption` table (assuming 'video' table exists)
CREATE TABLE `caption` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `video_id` int(11) NOT NULL,
  `time_start` int(11) DEFAULT NULL,
  `time_end` int(11) DEFAULT NULL,
  `text` varchar(512) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `caption_video_FK` (`video_id`),
  CONSTRAINT `caption_video_FK` FOREIGN KEY (`video_id`) REFERENCES `video` (`id`)
);

-- Step 4: Insert sample data
-- INSERT INTO yt_channel(channel_id, name, description, views, subscribers, language_id, should_crawl, last_crawled) VALUES ('UCMNMJW01ZNlSERud6oUnMyg', 'Naturen i Danmark', 'blabla', 756786, 8260, 2, 1, NOW());
-- INSERT INTO video(video_id, description, published_at, channel_id, thumbnail_url, tags, duration, language_id, vtt, plain_text) VALUES ('EWnStY9O4CA', 'blablabla', NOW(), 1, 'https://i.ytimg.com/vi/EWnStY9O4CA/hqdefault.jpg', 'tag1, tag2', 609, 2, 'vtt', 'plain text');