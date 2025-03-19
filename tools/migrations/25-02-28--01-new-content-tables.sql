CREATE TABLE `source_text` (
    `id` int NOT NULL AUTO_INCREMENT,
    `content` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `content_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '',
    PRIMARY KEY (`id`)
);

CREATE TABLE `new_text` (
    `id` int NOT NULL AUTO_INCREMENT,
    `content` MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `content_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '',
    PRIMARY KEY (`id`)
);

CREATE TABLE `zeeguu_test`.`source_type` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `type` VARCHAR(45) NULL,
    PRIMARY KEY (`id`)
);

INSERT INTO
    `zeeguu_test`.`source_type` (`type`)
VALUES
    ("Video");

INSERT INTO
    `zeeguu_test`.`source_type` (`type`)
VALUES
    ("Article");

CREATE TABLE `zeeguu_test`.`source` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `source_type_id` INT NULL,
    `source_text_id` INT NULL,
    `language_id` INT NULL,
    `fk_difficulty` INT NULL,
    `word_count` INT NULL,
    `broken` INT NULL,
    # using as boolean for now; might be counter in the future; code does not use that
    PRIMARY KEY (`id`),
    INDEX `source_ibfk_1_idx` (`language_id` ASC),
    CONSTRAINT `source_ibfk_1` FOREIGN KEY (`language_id`) REFERENCES `zeeguu_test`.`language` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    INDEX `source_ibfk_2_idx` (`source_text_id` ASC),
    CONSTRAINT `source_ibfk_2` FOREIGN KEY (`source_text_id`) REFERENCES `zeeguu_test`.`source_text` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    INDEX `source_ibfk_3_idx` (`source_type_id` ASC),
    CONSTRAINT `source_ibfk_3` FOREIGN KEY (`source_type_id`) REFERENCES `zeeguu_test`.`source_type` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_fragment` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `article_id` INT NOT NULL,
    `text_id` INT NOT NULL,
    `order` INT NULL,
    `formatting` VARCHAR(20) NULL,
    PRIMARY KEY (`id`),
    INDEX `article_fragment_ibfk_1_idx` (`article_id` ASC),
    CONSTRAINT `article_fragment_ibfk_1` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    INDEX `article_fragment_ibfk_2_idx` (`text_id` ASC),
    CONSTRAINT `article_fragment_ibfk_2` FOREIGN KEY (`text_id`) REFERENCES `zeeguu_test`.`new_text` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

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
    ("UserEditedText");

CREATE TABLE `bookmark_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `text_id` INT NOT NULL,
    `context_type_id` INT DEFAULT NULL,
    `language_id` INT DEFAULT NULL,
    `right_ellipsis` TINYINT DEFAULT NULL,
    `left_ellipsis` TINYINT DEFAULT NULL,
    `sentence_i` INT DEFAULT NULL,
    `token_i` INT DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `language_id` (`language_id`),
    CONSTRAINT `bookmark_context_ibfk_1` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`),
    KEY `text_id` (`text_id`),
    CONSTRAINT `bookmark_context_ibfk_2` FOREIGN KEY (`text_id`) REFERENCES `zeeguu_test`.`new_text` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
    KEY `context_type_id` (`context_type_id`),
    CONSTRAINT `bookmark_context_ibfk_3` FOREIGN KEY (`context_type_id`) REFERENCES `context_type` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_fragment_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `bookmark_id` INT NULL,
    `article_fragment_id` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `article_fragment_context_ibfk_1_idx` (`bookmark_id` ASC),
    INDEX `article_fragment_context_ibfk_2_idx` (`article_fragment_id` ASC),
    CONSTRAINT `article_fragment_context_ibfk_1` FOREIGN KEY (`bookmark_id`) REFERENCES `zeeguu_test`.`bookmark` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
    CONSTRAINT `article_fragment_context_ibfk_2` FOREIGN KEY (`article_fragment_id`) REFERENCES `zeeguu_test`.`article_fragment` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_summary_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `bookmark_id` INT NULL,
    `article_id` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `article_summary_context_ibfk_1_idx` (`bookmark_id` ASC),
    INDEX `article_summary_context_ibfk_2_idx` (`article_id` ASC),
    CONSTRAINT `article_summary_context_ibfk_1` FOREIGN KEY (`bookmark_id`) REFERENCES `zeeguu_test`.`bookmark` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
    CONSTRAINT `article_summary_context_ibfk_2` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE `zeeguu_test`.`article_title_context` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `bookmark_id` INT NULL,
    `article_id` INT NULL,
    PRIMARY KEY (`id`),
    INDEX `article_title_context_ibfk_1_idx` (`bookmark_id` ASC),
    INDEX `article_title_context_ibfk_2_idx` (`article_id` ASC),
    CONSTRAINT `article_title_context_ibfk_1` FOREIGN KEY (`bookmark_id`) REFERENCES `zeeguu_test`.`bookmark` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
    CONSTRAINT `article_title_context_ibfk_2` FOREIGN KEY (`article_id`) REFERENCES `zeeguu_test`.`article` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
);

ALTER TABLE
    `zeeguu_test`.`bookmark`
ADD
    COLUMN `context_id` INT NULL DEFAULT NULL
AFTER
    `translation_id`,
ADD
    COLUMN `source_id` INT NULL DEFAULT NULL
AFTER
    `context_id`,
ADD
    INDEX `bookmark_ibfk_7_idx` (`context_id` ASC),
ADD
    INDEX `bookmark_ibfk_8_ind` (`source_id` ASC),
ADD
    CONSTRAINT `bookmark_ibfk_7` FOREIGN KEY (`context_id`) REFERENCES `zeeguu_test`.`bookmark_context` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
ADD
    CONSTRAINT `bookmark_ibfk_8` FOREIGN KEY (`source_id`) REFERENCES `zeeguu_test`.`source` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION;

# This query might time out with on default settings.
ALTER TABLE
    `zeeguu_test`.`article`
ADD
    COLUMN `source_id` INT NULL
AFTER
    `id`,
ADD
    INDEX `article_ibfk_6_idx` (`source_id` ASC),
ADD
    CONSTRAINT `article_ibfk_6` FOREIGN KEY (`source_id`) REFERENCES `zeeguu_test`.`source` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION;

## Create Indexes for HASH Matching
ALTER TABLE
    `zeeguu_test`.`source_text`
ADD
    UNIQUE INDEX `HASH_INDEX` (`content_hash` ASC);

ALTER TABLE
    `zeeguu_test`.`new_text`
ADD
    UNIQUE INDEX `HASH_INDEX` (`content_hash` ASC);

# ##                ##
# ## DO NOT RUN YET ##
# ##                ##
# CREATE TABLE `zeeguu_test`.`video_title_context`
# (
#     `id`          INT NOT NULL AUTO_INCREMENT,
#     `bookmark_id` INT NULL,
#     `video_id`    INT NULL,
#     PRIMARY KEY (`id`),
#     INDEX `video_title_context_ibfk_1_idx` (`bookmark_id` ASC),
#     INDEX `video_title_context_ibfk_2_idx` (`video_id` ASC),
#     CONSTRAINT `video_title_context_ibfk_1` FOREIGN KEY (`bookmark_id`) REFERENCES `zeeguu_test`.`bookmark` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
#     CONSTRAINT `video_title_context_ibfk_2` FOREIGN KEY (`video_id`) REFERENCES `zeeguu_test`.`video` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
# );
#
# CREATE TABLE `zeeguu_test`.`web_fragment_context`
# (
#     `id`              INT NOT NULL AUTO_INCREMENT,
#     `bookmark_id`     INT NULL,
#     `web_fragment_id` INT NULL,
#     PRIMARY KEY (`id`),
#     INDEX `web_fragment_context_ibfk_1_idx` (`bookmark_id` ASC),
#     INDEX `web_fragment_context_ibfk_2_idx` (`web_fragment_id` ASC),
#     CONSTRAINT `web_fragment_context_ibfk_1` FOREIGN KEY (`bookmark_id`) REFERENCES `zeeguu_test`.`bookmark` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
#     CONSTRAINT `web_fragment_context_ibfk_2` FOREIGN KEY (`web_fragment_id`) REFERENCES `zeeguu_test`.`web_fragment` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
# );