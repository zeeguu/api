-- The dialogue of an audio lesson, as a text a learner can read in the reader.
--
-- The dialogue is an article row of its own, made the first time a learner asks
-- to read it and then shared by everyone who heard that lesson, so the reader's
-- translation, bookmarks and exercises work on it unchanged.
--
-- The article has one fragment per spoken line. speakers says who says each
-- fragment, in order ("Man", "Woman"), so the speakers never become words of
-- the text (tokens, bookmark contexts, text-to-speech).
--
-- Deleting the article deletes this row (the next request makes a new one);
-- deleting the lesson deletes this row too.

CREATE TABLE article_dialogue (
    article_id INT NOT NULL,
    audio_lesson_dialogue_id INT NOT NULL,
    speakers JSON NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (article_id),
    UNIQUE KEY uq_article_dialogue_lesson (audio_lesson_dialogue_id),
    CONSTRAINT fk_article_dialogue_article FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE CASCADE,
    CONSTRAINT fk_article_dialogue_lesson FOREIGN KEY (audio_lesson_dialogue_id) REFERENCES audio_lesson_dialogue (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
