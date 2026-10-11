-- Cache for Stanza-tokenized caption text so /user_video doesn't re-tokenize
-- every caption on every request (a captioned 16-min video has hundreds of
-- captions, each one a Stanza call -- it was the dominant cost of the
-- ~2-second /user_video response observed on share-to-video traffic).
--
-- Captions are immutable after ingestion, so entries are populated lazily on
-- first read and never invalidated. delete_older_than() exists for housekeeping.

CREATE TABLE caption_tokenization_cache (
    caption_id     INT NOT NULL PRIMARY KEY,
    tokenized_text MEDIUMTEXT,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_caption_tok_cache_caption_id
        FOREIGN KEY (caption_id) REFERENCES caption (id) ON DELETE CASCADE
);
