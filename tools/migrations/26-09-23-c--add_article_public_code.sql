-- Article links without numeric ids: zeeguu.org/read/<code>.
--
-- One random 10-char code per article (62^10), its public address; the same
-- link for every reader. Written the first time an article gets a link, never
-- per open. Cascades with the article: a code must not keep an article from
-- being pruned (so it is NOT in article_pruning.PROTECTING_TABLES).
--
-- Supersedes article_share_link (one code per user x article), which stays only
-- to resolve the ?id=…&s=… links handed out on 2026-09-23.
CREATE TABLE article_public_code (
    article_id INT NOT NULL PRIMARY KEY,
    code VARCHAR(16) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_article_public_code_code (code),
    CONSTRAINT fk_article_public_code_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE
) COLLATE utf8_bin;
