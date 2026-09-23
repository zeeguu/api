-- Article links without numeric ids: zeeguu.org/read/<article code>?by=<user code>.
--
-- article_public_code: one random 10-char code per article (62^10), its public
-- address. Written the first time an article gets a link, never per open.
-- Cascades with the article: a code must not keep an article from being pruned.
--
-- user_share_code: one short code per user, the "shared by" credit.
--
-- Supersedes article_share_link (one row per user x article), which stays only
-- to resolve the ?id=…&s=… links handed out on 2026-09-23.
CREATE TABLE article_public_code (
    article_id INT NOT NULL PRIMARY KEY,
    code VARCHAR(16) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_article_public_code_code (code),
    CONSTRAINT fk_article_public_code_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE
) COLLATE utf8_bin;

CREATE TABLE user_share_code (
    user_id INT NOT NULL PRIMARY KEY,
    code VARCHAR(16) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_share_code_code (code),
    CONSTRAINT fk_user_share_code_user FOREIGN KEY (user_id) REFERENCES user(id)
) COLLATE utf8_bin;
