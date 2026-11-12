-- Short texts a learner brings to read word by word (a WhatsApp message, a
-- paragraph from a mail), pasted or shared from another app.
-- short_text: the content, once (a Source of type ShortText dedups it).
-- user_short_text: a learner's own list; deleting the row forgets the text.

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
    PRIMARY KEY (id),
    UNIQUE KEY short_text_source_unique (source_id),
    CONSTRAINT fk_short_text_source FOREIGN KEY (source_id) REFERENCES source (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

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
