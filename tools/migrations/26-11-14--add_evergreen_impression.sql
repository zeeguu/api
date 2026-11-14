-- What the Evergreen tab has shown each learner, so every visit can bring
-- something new: an article shown on an earlier day and not opened drops
-- behind ones never seen. times_shown counts days, not page loads.

CREATE TABLE evergreen_impression (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    article_id INT NOT NULL,
    first_shown DATETIME NOT NULL,
    last_shown DATETIME NOT NULL,
    times_shown INT NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_evergreen_impression_user_article (user_id, article_id),
    KEY ix_evergreen_impression_article (article_id),
    CONSTRAINT fk_evergreen_impression_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    CONSTRAINT fk_evergreen_impression_article FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- The recommender filters on (language_id, article_type); without this it
-- scans the language's whole history.
CREATE INDEX ix_article_language_type ON article (language_id, article_type);
