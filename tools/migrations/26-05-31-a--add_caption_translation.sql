-- v1.5: translated captions for a shared video.
-- A `caption_translation_set` is a per-(video, target_language, target_cefr) bundle that owns
-- per-original-caption translated text rows. Timing stays on the parent `caption` rows so we
-- don't duplicate it (the player aligns by original time_start/time_end). Status drives the
-- async translation job (mirrors the daily-audio-lesson status pattern).

CREATE TABLE `caption_translation_set` (
    `id` int NOT NULL AUTO_INCREMENT,
    `video_id` int NOT NULL,
    `target_language_id` int NOT NULL,
    `cefr_level` enum('A1','A2','B1','B2','C1','C2') NOT NULL,
    `status` enum('pending','translating','ready','error') NOT NULL DEFAULT 'pending',
    `error_message` varchar(500) DEFAULT NULL,
    `created_at` datetime NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_caption_translation_set_video_lang_cefr`
        (`video_id`, `target_language_id`, `cefr_level`),
    CONSTRAINT `fk_caption_translation_set_video`
        FOREIGN KEY (`video_id`) REFERENCES `video` (`id`),
    CONSTRAINT `fk_caption_translation_set_target_language`
        FOREIGN KEY (`target_language_id`) REFERENCES `language` (`id`)
);

CREATE TABLE `caption_translation` (
    `id` int NOT NULL AUTO_INCREMENT,
    `set_id` int NOT NULL,
    `caption_id` int NOT NULL,
    `text_id` int NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_caption_translation_set_caption` (`set_id`, `caption_id`),
    CONSTRAINT `fk_caption_translation_set`
        FOREIGN KEY (`set_id`) REFERENCES `caption_translation_set` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_caption_translation_caption`
        FOREIGN KEY (`caption_id`) REFERENCES `caption` (`id`),
    CONSTRAINT `fk_caption_translation_text`
        FOREIGN KEY (`text_id`) REFERENCES `new_text` (`id`)
);
