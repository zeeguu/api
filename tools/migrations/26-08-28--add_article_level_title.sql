-- Per-level headlines, alongside the per-level summaries added on 26-08-12.
--
-- Before on-demand simplification the feed card DID show a level-appropriate
-- title: the overlay borrowed both title and summary off the level-matched
-- simplified child article. When the crawl stopped generating those children
-- (commit 0d047e32), article_level_summary replaced the summary half and nothing
-- replaced the title half — so the card headline went back to the publisher's
-- own, at every level.
--
-- That matters more than it sounds: the default feed view is Headlines, which
-- renders the title and no summary at all, so with no per-level title the CEFR
-- selector changes nothing a default-view reader can see.
--
-- Columns are nullable: every existing row has no title, and a level whose title
-- comes back in the wrong language is dropped while its summary is kept. Both
-- cases fall back to the article's own title.
ALTER TABLE article_level_summary
    ADD COLUMN title TEXT AFTER tokenized_summary,
    ADD COLUMN tokenized_title JSON AFTER title;

-- article_level_title_context: the tap-to-translate context join for those
-- headlines. Separate from article_level_summary_context even though both point
-- at the same article_level_summary row — a level's title and its summary are
-- two different token streams, and sharing one join table would return the
-- title's bookmarks when highlighting the summary.
CREATE TABLE article_level_title_context (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bookmark_id INT NOT NULL,
    article_level_summary_id INT,
    CONSTRAINT fk_altc_bookmark FOREIGN KEY (bookmark_id) REFERENCES bookmark (id),
    CONSTRAINT fk_altc_summary FOREIGN KEY (article_level_summary_id) REFERENCES article_level_summary (id) ON DELETE CASCADE,
    -- One context row per (bookmark, level title): makes a concurrent-insert
    -- race fail with IntegrityError (which find_or_create catches + re-queries)
    -- instead of silently creating a duplicate that later breaks .one().
    UNIQUE KEY uq_altc_bookmark_title (bookmark_id, article_level_summary_id)
);

-- New context type so the bookmark/context pipeline can dispatch to the join above.
INSERT INTO context_type (type) VALUES ('ArticleLevelTitle');
