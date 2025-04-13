-- Assuming 'language' table exists
CREATE TABLE `yt_channel` (
  `id` int NOT NULL AUTO_INCREMENT,
  `channel_id` varchar(512) NOT NULL,
  `name` varchar(512) DEFAULT NULL,
  `description` mediumtext,
  `views` bigint unsigned DEFAULT NULL,
  `subscribers` int unsigned DEFAULT NULL,
  `language_id` int DEFAULT NULL,
  `thumbnail_url_id` int DEFAULT NULL,
  `should_crawl` int DEFAULT NULL,
  `last_crawled` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `yt_channel_unique_channel_id` (`channel_id`),
  KEY `yt_channel_language_FK` (`language_id`),
  KEY `yt_channel_thumbnail_url_id` (`thumbnail_url_id`),
  CONSTRAINT `yt_channel_language_FK` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`),
  CONSTRAINT `yt_channel_thumbnail_url_id` FOREIGN KEY (`thumbnail_url_id`) REFERENCES `url` (`id`)
);

-- Assuming 'yt_channel' table exists
CREATE TABLE `video` (
  `id` int NOT NULL AUTO_INCREMENT,
  `source_id` int NULL,
  `video_unique_key` varchar(512) NOT NULL,
  `title` varchar(512) NULL,
  `description` mediumtext,
  `published_at` datetime DEFAULT NULL,
  `channel_id` int DEFAULT NULL,
  `thumbnail_url_id` int DEFAULT NULL,
  `duration` int DEFAULT NULL,
  `language_id` int DEFAULT NULL,
  `vtt` mediumtext,
  `broken` int DEFAULT NULL,
  `crawled_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `video_unique_key_constraint` (`video_unique_key`),
  KEY `video_language_FK` (`language_id`),
  KEY `video_yt_channel_FK` (`channel_id`),
  KEY `source_id_FK` (`source_id`),
  KEY `thumbnail_url_id` (`thumbnail_url_id`),
  CONSTRAINT `source_id_FK` FOREIGN KEY (`source_id`) REFERENCES `zeeguu_test`.`source` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `video_language_FK` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`),
  CONSTRAINT `video_yt_channel_FK` FOREIGN KEY (`channel_id`) REFERENCES `yt_channel` (`id`),
  CONSTRAINT `video_thumbnail_url_id` FOREIGN KEY (`thumbnail_url_id`) REFERENCES `url` (`id`)
);

-- Assuming 'video' table exists
CREATE TABLE `caption` (
  `id` int NOT NULL AUTO_INCREMENT,
  `video_id` int NOT NULL,
  `text_id` int NULL,
  `time_start` int DEFAULT NULL,
  `time_end` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `caption_video_FK` (`video_id`),
  KEY `text_FK` (`text_id`),
  CONSTRAINT `caption_video_FK` FOREIGN KEY (`video_id`) REFERENCES `video` (`id`),
  CONSTRAINT `text_FK` FOREIGN KEY (`text_id`) REFERENCES `new_text` (`id`)
);

CREATE TABLE `video_tag` (
  `id` int NOT NULL AUTO_INCREMENT,
  `tag` varchar(512) NOT NULL,
  PRIMARY KEY (`id`)
);

-- Assuming 'video' and 'video_tag' tables exist
CREATE TABLE `video_tag_map` (
  `video_id` int NOT NULL,
  `tag_id` int NOT NULL,
  PRIMARY KEY (`video_id`, `tag_id`),
  KEY `video_tag_map_video_FK` (`video_id`),
  KEY `video_tag_map_tag_FK` (`tag_id`),
  CONSTRAINT `video_tag_map_video_FK` FOREIGN KEY (`video_id`) REFERENCES `video` (`id`),
  CONSTRAINT `video_tag_map_tag_FK` FOREIGN KEY (`tag_id`) REFERENCES `video_tag` (`id`)
);

CREATE TABLE `video_topic_map` (
  `video_id` int NOT NULL,
  `topic_id` int NOT NULL,
  `origin_type` int NOT NULL,
  PRIMARY KEY (`video_id`, `topic_id`),
  KEY `video_topic_map_video_FK` (`video_id`),
  KEY `video_topic_map_tag_FK` (`topic_id`),
  CONSTRAINT `video_topic_map_video_FK` FOREIGN KEY (`video_id`) REFERENCES `video` (`id`),
  CONSTRAINT `video_topic_map_tag_FK` FOREIGN KEY (`topic_id`) REFERENCES `topic` (`id`)
);

CREATE TABLE `user_video` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `video_id` int NOT NULL,
  `opened` datetime DEFAULT NULL,
  `liked` boolean DEFAULT NULL,
  `playback_position` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_video_user_FK` (`user_id`),
  KEY `user_video_video_FK` (`video_id`),
  CONSTRAINT `user_video_user_FK` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `user_video_video_FK` FOREIGN KEY (`video_id`) REFERENCES `video` (`id`)
);

CREATE TABLE `user_watching_session` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `video_id` int NOT NULL,
  `start_time` datetime DEFAULT NULL,
  `duration` int DEFAULT NULL,
  `last_action_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_watching_session_user_FK` (`user_id`),
  KEY `user_watching_session_video_FK` (`video_id`),
  CONSTRAINT `user_watching_session_user_FK` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `user_watching_session_video_FK` FOREIGN KEY (`video_id`) REFERENCES `video` (`id`)
);

############# This should maybe be in a file where the other contexts are created idk ###############
 CREATE TABLE `video_caption_context` (
  `id` int NOT NULL AUTO_INCREMENT,
  `bookmark_id` int NULL,
  `caption_id` int NULL,
  PRIMARY KEY (`id`),
  KEY `video_caption_context_ibfk_1_idx` (`bookmark_id` ASC),
  KEY `video_caption_context_ibfk_2_idx` (`caption_id` ASC),
  CONSTRAINT `video_caption_context_ibfk_1` FOREIGN KEY (`bookmark_id`) REFERENCES `bookmark` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
  CONSTRAINT `video_caption_context_ibfk_2` FOREIGN KEY (`caption_id`) REFERENCES `caption` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
 );