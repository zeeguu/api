-- Short texts a learner brings to read word by word (a WhatsApp message, a
-- paragraph from a mail), pasted or shared from another app.
-- short_text: the content, once (a Source of type ShortText dedups it).
-- user_short_text: a learner's own list. When the last learner forgets a
-- text, the text itself is deleted.

INSERT INTO source_type (type)
SELECT 'ShortText' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM source_type WHERE type = 'ShortText');

INSERT INTO context_type (type)
SELECT 'ShortText' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM context_type WHERE type = 'ShortText');

CREATE TABLE short_text (
    id INT NOT NULL AUTO_INCREMENT,
    source_id INT NOT NULL,
    created_at DATETIME NOT NULL,
    -- the reader's tokens as JSON, computed on the first read
    tokenized_paragraphs MEDIUMTEXT DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY short_text_source_unique (source_id),
    CONSTRAINT fk_short_text_source FOREIGN KEY (source_id) REFERENCES source (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- The whole text translated, kept per language: translators bill every call.
CREATE TABLE short_text_translation (
    id INT NOT NULL AUTO_INCREMENT,
    short_text_id INT NOT NULL,
    language_id INT NOT NULL,
    content MEDIUMTEXT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY short_text_translation_unique (short_text_id, language_id),
    CONSTRAINT fk_short_text_translation_short_text FOREIGN KEY (short_text_id) REFERENCES short_text (id),
    CONSTRAINT fk_short_text_translation_language FOREIGN KEY (language_id) REFERENCES language (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE user_short_text (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    short_text_id INT NOT NULL,
    created_at DATETIME NOT NULL,
    last_opened_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY user_short_text_unique (user_id, short_text_id),
    KEY ix_user_short_text_last_opened (user_id, last_opened_at),
    CONSTRAINT fk_user_short_text_user FOREIGN KEY (user_id) REFERENCES user (id),
    CONSTRAINT fk_user_short_text_short_text FOREIGN KEY (short_text_id) REFERENCES short_text (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
