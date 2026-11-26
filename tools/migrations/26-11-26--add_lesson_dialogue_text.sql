-- The dialogue of an audio lesson, as a text a learner reads line by line.
-- A Source of its own type, like a short text: taps carry its source_id and
-- the LessonDialogue context type. Made the first time a learner asks to read
-- the dialogue, then shared by everyone who heard that lesson.
--
-- One line of the content per spoken line; speakers says who says each
-- ("Man", "Woman"), in order, so the speakers never become words of the text.

INSERT INTO source_type (type)
SELECT 'LessonDialogue' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM source_type WHERE type = 'LessonDialogue');

INSERT INTO context_type (type)
SELECT 'LessonDialogue' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM context_type WHERE type = 'LessonDialogue');

CREATE TABLE lesson_dialogue_text (
    id INT NOT NULL AUTO_INCREMENT,
    source_id INT NOT NULL,
    audio_lesson_dialogue_id INT NOT NULL,
    speakers JSON NOT NULL,
    created_at DATETIME NOT NULL,
    -- the reader's tokens as JSON, computed on the first read
    tokenized_paragraphs MEDIUMTEXT DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY lesson_dialogue_text_source_unique (source_id),
    UNIQUE KEY lesson_dialogue_text_lesson_unique (audio_lesson_dialogue_id),
    CONSTRAINT fk_lesson_dialogue_text_source FOREIGN KEY (source_id) REFERENCES source (id),
    CONSTRAINT fk_lesson_dialogue_text_lesson FOREIGN KEY (audio_lesson_dialogue_id) REFERENCES audio_lesson_dialogue (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
