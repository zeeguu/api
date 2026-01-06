-- Add cached tokenized content to bookmark_context
-- This avoids running Stanza NLP on every exercise request

ALTER TABLE bookmark_context
ADD COLUMN cached_tokenized JSON DEFAULT NULL;

-- Index not needed since we always lookup by id (primary key)
