-- Flip the upload<->article link onto the article_upload table.
--
-- Reality: one real-world article (one publisher URL) can be uploaded by MANY
-- users (e.g. a subscriber captures the full body; a non-subscriber captures
-- only the teaser). A single `article.source_upload_id` (added in #688) can
-- only reference ONE upload, so it models the relationship backwards. The
-- correct shape is many uploads : one article, i.e. the FK belongs here, on
-- the upload, pointing at the canonical article that lives at the same URL.
--
-- See docs/future-work/article-body-provenance-and-sharing.md. This is
-- ADDITIVE: `article.source_upload_id` is left in place during the transition
-- (a later migration removes it once all readers move over).
ALTER TABLE article_upload
    ADD COLUMN article_id INT NULL
        COMMENT 'The canonical article at this upload''s URL (many uploads : one article). NULL until an article exists at the URL.',
    ADD CONSTRAINT fk_article_upload_article
        FOREIGN KEY (article_id) REFERENCES article(id);

-- Backfill: link each upload to the article that already sits at the same URL
-- (article.url_id is UNIQUE, so this matches at most one). Uploads whose URL has
-- never been crawled stay NULL. NOTE: this is NOT the reverse of
-- article.source_upload_id — that column lives on the simplified CHILD (which
-- has a synthetic zeeguu.org URL), not on the canonical article.
UPDATE article_upload au
    JOIN article a ON a.url_id = au.url_id
SET au.article_id = a.id
WHERE au.article_id IS NULL;
