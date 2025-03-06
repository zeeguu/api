CREATE TABLE `zeeguu_test`.`plaintext` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `text` MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NULL,
    `language_id` INT NULL,
    `fk_difficulty` INT NULL,
    `word_count` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `plaintext_ibfk_1_idx` (`language_id` ASC),
    CONSTRAINT `plaintext_ibfk_1` FOREIGN KEY (`language_id`) REFERENCES `zeeguu_test`.`language` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_fragment` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `article_id` INT NOT NULL,
    `order` INT NULL,
    `text` MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NULL,
    `formatting` VARCHAR(20) NULL,
    PRIMARY KEY (`id`),
    INDEX `article_fragment_ibfk_1_idx` (`article_id` ASC),
    CONSTRAINT `article_fragment_ibfk_1` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `context` (
    `id` int NOT NULL AUTO_INCREMENT,
    `content` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `content_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '',
    `language_id` int DEFAULT NULL,
    `right_ellipsis` tinyint DEFAULT NULL,
    `left_ellipsis` tinyint DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `content_hash` (`content_hash`),
    KEY `language_id` (`language_id`),
    CONSTRAINT `context_ibfk_1` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`)
);

CREATE TABLE `zeeguu_test`.`article_fragment_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `context_id` INT NULL,
    `article_fragment_id` INT NULL,
    `sentence_i` INT NULL,
    `token_i` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `article_fragment_context_ibfk_1_idx` (`context_id` ASC),
    INDEX `article_fragment_context_ibfk_2_idx` (`article_fragment_id` ASC),
    CONSTRAINT `article_fragment_context_ibfk_1` FOREIGN KEY (`context_id`) REFERENCES `zeeguu_test`.`context` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `article_fragment_context_ibfk_2` FOREIGN KEY (`article_fragment_id`) REFERENCES `zeeguu_test`.`article_fragment` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_summary_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `context_id` INT NULL,
    `article_id` INT NULL,
    `sentence_i` INT NULL,
    `token_i` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `article_summary_context_ibfk_1_idx` (`context_id` ASC),
    INDEX `article_summary_context_ibfk_2_idx` (`article_id` ASC),
    CONSTRAINT `article_summary_context_ibfk_1` FOREIGN KEY (`context_id`) REFERENCES `zeeguu_test`.`context` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `article_summary_context_ibfk_2` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_title_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `context_id` INT NULL,
    `article_id` INT NULL,
    `sentence_i` INT NULL,
    `token_i` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `article_title_context_ibfk_1_idx` (`context_id` ASC),
    INDEX `article_title_context_ibfk_2_idx` (`article_id` ASC),
    CONSTRAINT `article_title_context_ibfk_1` FOREIGN KEY (`context_id`) REFERENCES `zeeguu_test`.`context` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `article_title_context_ibfk_2` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`video_title_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `context_id` INT NULL,
    `video_id` INT NULL,
    `sentence_i` INT NULL,
    `token_i` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `video_title_context_ibfk_1_idx` (`context_id` ASC),
    INDEX `video_title_context_ibfk_2_idx` (`video_id` ASC),
    CONSTRAINT `video_title_context_ibfk_1` FOREIGN KEY (`context_id`) REFERENCES `zeeguu_test`.`context` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `video_title_context_ibfk_2` FOREIGN KEY (`video_id`) REFERENCES `zeeguu_test`.`video` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`web_fragment_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `context_id` INT NULL,
    `web_fragment_id` INT NULL,
    `sentence_i` INT NULL,
    `token_i` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `web_fragment_context_ibfk_1_idx` (`context_id` ASC),
    INDEX `web_fragment_context_ibfk_2_idx` (`video_id` ASC),
    CONSTRAINT `web_fragment_context_ibfk_1` FOREIGN KEY (`context_id`) REFERENCES `zeeguu_test`.`context` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT `web_fragment_context_ibfk_2` FOREIGN KEY (`web_fragment_id`) REFERENCES `zeeguu_test`.`web_fragment` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

ALTER TABLE
    `zeeguu_test`.`article` DROP FOREIGN KEY `article_ibfk_5`;

ALTER TABLE
    `zeeguu_test`.`article`
ADD
    COLUMN `plaintext_id` INT NULL DEFAULT NULL
AFTER
    `title`,
    CHANGE COLUMN `authors` `authors` VARCHAR(1024) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_bin' NULL DEFAULT NULL,
    CHANGE COLUMN `img_url_id` `main_img_url_id` INT NULL DEFAULT NULL;

ALTER TABLE
    `zeeguu_test`.`article`
ADD
    CONSTRAINT `article_ibfk_5` FOREIGN KEY (`main_img_url_id`) REFERENCES `zeeguu_test`.`url` (`id`),
ADD
    CONSTRAINT `article_ibfk_6` FOREIGN KEY (`plaintext_id`) REFERENCES `zeeguu_test`.`plaintext` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION;

CREATE TABLE `zeeguu_test`.`context_type` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `type` VARCHAR(45) NULL,
    PRIMARY KEY (`id`)
);

INSERT INTO
    `zeeguu_test`.`context_type` (`type`)
VALUES
    ("ArticleFragment");

INSERT INTO
    `zeeguu_test`.`context_type` (`type`)
VALUES
    ("ArticleTitle");

INSERT INTO
    `zeeguu_test`.`context_type` (`type`)
VALUES
    ("ArticleSummary");

INSERT INTO
    `zeeguu_test`.`context_type` (`type`)
VALUES
    ("VideoTitle");

INSERT INTO
    `zeeguu_test`.`context_type` (`type`)
VALUES
    ("VideoSubtitle");

INSERT INTO
    `zeeguu_test`.`context_type` (`type`)
VALUES
    ("WebFragment");

INSERT INTO
    `zeeguu_test`.`context_type` (`type`)
VALUES
    ("UserEdited");

ALTER TABLE
    `zeeguu_test`.`bookmark`
ADD
    COLUMN `context_id` INT NULL DEFAULT NULL
AFTER
    `translation_id`,
ADD
    COLUMN `context_type` VARCHAR(45) NULL DEFAULT NULL
AFTER
    `context_id`,
ADD
    INDEX `bookmark_ibfk_7_idx` (`context_id` ASC);

ALTER TABLE
    `zeeguu_test`.`bookmark`
ADD
    CONSTRAINT `bookmark_ibfk_7` FOREIGN KEY (`context_id`) REFERENCES `zeeguu_test`.`context` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION;