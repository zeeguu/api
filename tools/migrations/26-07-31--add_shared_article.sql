-- On-platform "share an article with a friend".
--
-- One row = one friend sending one article to another, with an optional note.
-- article_id is the ORIGINAL/parent article id (never the sharer's adapted or
-- translated copy) so the recipient's reader can adapt it to their own language
-- and level on open. read_at / dismissed_at track the recipient's inbox state.
CREATE TABLE shared_article (
    id INT AUTO_INCREMENT PRIMARY KEY,
    from_user_id INT NOT NULL,
    to_user_id INT NOT NULL,
    article_id INT NOT NULL,
    note VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME,
    dismissed_at DATETIME,
    FOREIGN KEY (from_user_id) REFERENCES user(id),
    FOREIGN KEY (to_user_id) REFERENCES user(id),
    FOREIGN KEY (article_id) REFERENCES article(id)
);
