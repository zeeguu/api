-- Public share links for articles ("copy link / share elsewhere").
--
-- One row per (user, article). The link is /read/article?id=<article_id>&s=<code>;
-- the opaque code lets the account-less public page say who shared it, and
-- unlocks uploaded (private) texts for whoever was sent the link.
--
-- article_id is RESTRICT like the other user-data tables, and is listed in
-- article_pruning.PROTECTING_TABLES: a link someone posted must keep working.
CREATE TABLE article_share_link (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(16) NOT NULL,
    user_id INT NOT NULL,
    article_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_article_share_link_code (code),
    UNIQUE KEY uq_article_share_link_user_article (user_id, article_id),
    CONSTRAINT fk_article_share_link_user FOREIGN KEY (user_id) REFERENCES user(id),
    CONSTRAINT fk_article_share_link_article FOREIGN KEY (article_id) REFERENCES article(id)
) COLLATE utf8_bin;
