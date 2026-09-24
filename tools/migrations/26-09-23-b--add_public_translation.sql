-- Cached translations for the account-less shared-article page.
--
-- The public page sends a word's position in an article, never text; the
-- server reads the word from the article and caches the answer here, so each
-- (article, position, target language) is translated once. This bounds what a
-- scripted visitor can cost us to the words that exist in public articles, and
-- makes repeat taps in a shared article free.
--
-- article_id cascades: a cache must not stop the nightly prune from removing
-- an article (and is deliberately NOT in article_pruning.PROTECTING_TABLES).
CREATE TABLE public_translation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT NOT NULL,
    part VARCHAR(32) NOT NULL,
    paragraph_i INT NOT NULL,
    sent_i INT NOT NULL,
    token_i INT NOT NULL,
    total_tokens INT NOT NULL,
    partner_token_i INT NOT NULL DEFAULT -1,
    to_language_id INT NOT NULL,
    translation TEXT NOT NULL,
    source VARCHAR(255),
    alternatives_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_public_translation_position
        (article_id, part, paragraph_i, sent_i, token_i, total_tokens, partner_token_i, to_language_id),
    CONSTRAINT fk_public_translation_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE,
    CONSTRAINT fk_public_translation_language FOREIGN KEY (to_language_id) REFERENCES language(id)
) COLLATE utf8_bin;
