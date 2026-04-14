-- Per-user lightweight ingestion entity for articles sent from the extension
-- (and later iOS share). Holds the raw HTML client-side scrape so we can
-- derive simplified/adapted/promoted Article rows on user choice, without
-- paying full ingestion cost (Stanza, CEFR LLM, fragments, topics) up front.
-- See docs/future-work/extension-ingestion-unification.md

CREATE TABLE article_upload (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    url_id INT NOT NULL,
    language_id INT NOT NULL,
    title VARCHAR(512) DEFAULT NULL,
    raw_html MEDIUMTEXT,
    text_content MEDIUMTEXT,
    image_url VARCHAR(2048) DEFAULT NULL,
    author VARCHAR(256) DEFAULT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_article_upload_user_id (user_id),
    KEY ix_article_upload_url_id (url_id),
    CONSTRAINT fk_article_upload_user FOREIGN KEY (user_id) REFERENCES user (id),
    CONSTRAINT fk_article_upload_url FOREIGN KEY (url_id) REFERENCES url (id),
    CONSTRAINT fk_article_upload_language FOREIGN KEY (language_id) REFERENCES language (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

-- Back-reference from Article to the upload it was derived from.
-- Nullable: normal feed / teacher-uploaded articles don't have one.
ALTER TABLE article
    ADD COLUMN source_upload_id INT DEFAULT NULL,
    ADD CONSTRAINT fk_article_source_upload
        FOREIGN KEY (source_upload_id) REFERENCES article_upload (id);
