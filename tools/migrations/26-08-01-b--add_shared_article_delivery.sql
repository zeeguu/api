-- The recipient's personalized derivative for a share ("the multiplexer out").
--
-- article_id stays the canonical article (the handle + "See original"). These
-- add the copy the recipient actually reads: generated from the SHARER's upload
-- body, in the recipient's delivery language at their level.
--   delivery_language_id : the language the recipient receives it in (source
--                          language if they learn it, else their primary).
--   delivery_article_id  : the generated derivative; NULL until it's ready.
--
-- See docs/future-work/article-body-provenance-and-sharing.md.
ALTER TABLE shared_article
    ADD COLUMN delivery_language_id INT NULL,
    ADD COLUMN delivery_article_id INT NULL,
    ADD CONSTRAINT fk_shared_article_delivery_language
        FOREIGN KEY (delivery_language_id) REFERENCES language(id),
    ADD CONSTRAINT fk_shared_article_delivery_article
        FOREIGN KEY (delivery_article_id) REFERENCES article(id);
