-- User MWE Override: allows users to disable incorrect MWE groupings
-- When a user "ungroups" an MWE, we store it here so future article loads
-- skip that mwe_group_id for this user
--
-- Uses sentence_hash (SHA256 of sentence text) instead of sentence_i
-- This survives article re-ordering and naturally invalidates if sentence is edited
--
-- Also stores mwe_expression (the actual words) for robust matching even if
-- mwe_group_id changes due to re-tokenization

CREATE TABLE user_mwe_override (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    article_id INT NOT NULL,
    sentence_hash VARCHAR(64) NOT NULL,
    mwe_expression VARCHAR(255) NOT NULL,
    disabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_article_sentence_mwe (user_id, article_id, sentence_hash, mwe_expression)
);
