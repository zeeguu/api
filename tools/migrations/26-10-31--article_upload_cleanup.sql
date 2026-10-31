-- What the cleanup of an upload removed (zeeguu/core/content_cleaning/upload_cleanup.py): the upload as it
-- came, and the keep/drop decision on each block, to check the cleanup and to train a cheaper classifier on.
-- Side tables, so article_upload is not rebuilt. They go with their upload.

CREATE TABLE article_upload_cleanup (
    upload_id INT NOT NULL,
    original_html MEDIUMTEXT,
    original_text MEDIUMTEXT,
    incomplete TINYINT(1) NOT NULL,
    incomplete_note TEXT,
    model VARCHAR(64) NOT NULL,
    prompt_version INT NOT NULL,
    seconds FLOAT DEFAULT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (upload_id),
    CONSTRAINT fk_article_upload_cleanup_upload FOREIGN KEY (upload_id) REFERENCES article_upload (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE article_upload_block (
    id INT NOT NULL AUTO_INCREMENT,
    upload_id INT NOT NULL,
    block_i INT NOT NULL,
    text TEXT NOT NULL,
    kept TINYINT(1) NOT NULL,
    reason VARCHAR(32) DEFAULT NULL,
    note TEXT,
    PRIMARY KEY (id),
    KEY ix_article_upload_block_upload_id (upload_id),
    CONSTRAINT fk_article_upload_block_upload FOREIGN KEY (upload_id) REFERENCES article_upload (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
