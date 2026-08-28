-- Per-level headlines, plus the rename that makes room for them.
--
-- WHY THE RENAME. article_level_summary reads as "the article's level" or
-- "article-level granularity"; the thing it stores is an article's text ADAPTED
-- TO a level. Adding a title to the same row makes "..._summary" wrong outright,
-- so the table becomes level_adapted_article_text and the two context types
-- become LevelAdaptedArticleSummary / LevelAdaptedArticleTitle.
--
-- WHY THE TITLES. Before on-demand simplification the feed card DID show a
-- level-appropriate headline: the overlay borrowed title and summary off the
-- level-matched simplified child article. When the crawl stopped generating
-- those children (commit 0d047e32), the per-level summary replaced the summary
-- half and nothing replaced the title half. That matters more than it sounds:
-- the default feed view is Headlines, which renders the title and NO summary, so
-- with no per-level title the CEFR selector changes nothing a default-view
-- reader can see.
--
-- Renaming is cheap here: bookmark_context rows point at context_type by id, and
-- UPDATE preserves the id, so the existing rows need no migration at all.
--
-- IF YOU ALREADY APPLIED 26-08-28--add_article_level_title.sql (an earlier draft
-- of this file, superseded by the rename), undo it first — it created an empty
-- table and empty columns that this file recreates under the right names:
--     DROP TABLE article_level_title_context;
--     ALTER TABLE article_level_summary DROP COLUMN title, DROP COLUMN tokenized_title;
--     DELETE FROM context_type WHERE type = 'ArticleLevelTitle';

RENAME TABLE article_level_summary TO level_adapted_article_text;
RENAME TABLE article_level_summary_context TO level_adapted_article_summary_context;

ALTER TABLE level_adapted_article_summary_context
    CHANGE COLUMN article_level_summary_id level_adapted_article_text_id INT;

-- The level's headline and its token stream. Nullable on purpose: every row
-- written before per-level titles has none, and a title dropped by the
-- wrong-language check leaves its summary in place. Both fall back to the
-- article's own title.
ALTER TABLE level_adapted_article_text
    ADD COLUMN title TEXT AFTER tokenized_summary,
    ADD COLUMN tokenized_title JSON AFTER title;

-- The tap-to-translate join for those headlines. Separate from the summary
-- context even though both point at the same level_adapted_article_text row: a
-- level's title and its summary are two different token streams, and one join
-- table for both would return the title's bookmarks when highlighting the
-- summary.
CREATE TABLE level_adapted_article_title_context (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bookmark_id INT NOT NULL,
    level_adapted_article_text_id INT,
    CONSTRAINT fk_latc_bookmark FOREIGN KEY (bookmark_id) REFERENCES bookmark (id),
    CONSTRAINT fk_latc_text FOREIGN KEY (level_adapted_article_text_id) REFERENCES level_adapted_article_text (id) ON DELETE CASCADE,
    -- One context row per (bookmark, level title): makes a concurrent-insert
    -- race fail with IntegrityError (which find_or_create catches + re-queries)
    -- instead of silently creating a duplicate that later breaks .one().
    UNIQUE KEY uq_latc_bookmark_title (bookmark_id, level_adapted_article_text_id)
);

-- Same row, new spelling: the id is preserved, so every bookmark_context already
-- pointing at it stays valid.
UPDATE context_type SET type = 'LevelAdaptedArticleSummary' WHERE type = 'ArticleLevelSummary';

INSERT INTO context_type (type) VALUES ('LevelAdaptedArticleTitle');
