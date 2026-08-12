-- Per-level preview summaries for the on-demand simplification flow.
--
-- Simplification is now on-demand: the crawl no longer pre-generates full
-- simplified article bodies for every CEFR level. But the feed card still wants
-- a LEVEL-APPROPRIATE, tappable summary for each learner. Previously that came
-- for free from the per-level simplified child articles (each carried its own
-- summary + tokenization + tap-context, keyed by the child's article_id). With
-- no children, we store the per-level summaries directly, cheaply.
--
-- article_level_summary: one short summary per (article, level-below-original).
-- The original-level summary stays in article.summary as the fallback.
CREATE TABLE article_level_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT NOT NULL,
    cefr_level ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2') NOT NULL,
    summary TEXT,
    tokenized_summary JSON,
    ai_generator_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_als_article FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE CASCADE,
    CONSTRAINT fk_als_ai_generator FOREIGN KEY (ai_generator_id) REFERENCES ai_generator (id),
    UNIQUE KEY uq_article_level (article_id, cefr_level)
);

-- article_level_summary_context: the tap-to-translate context join, mirroring
-- article_fragment_context. Anchors a bookmark to a SPECIFIC level's summary so
-- past-bookmark highlighting lands on the right tokens (summaries differ by
-- level, so token coordinates are not shared across levels).
CREATE TABLE article_level_summary_context (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bookmark_id INT NOT NULL,
    article_level_summary_id INT,
    CONSTRAINT fk_alsc_bookmark FOREIGN KEY (bookmark_id) REFERENCES bookmark (id),
    CONSTRAINT fk_alsc_summary FOREIGN KEY (article_level_summary_id) REFERENCES article_level_summary (id) ON DELETE CASCADE
);

-- New context type so the bookmark/context pipeline can dispatch to the join above.
INSERT INTO context_type (type) VALUES ('ArticleLevelSummary');
