-- Add UNIQUE(bookmark_id, <anchor_id>) to the bookmark/context join tables.
--
-- Each of these tables backs a copy-pasted find_or_create that (a) inherited an
-- 'except A or B' bug which only ever caught NoResultFound, and (b) had no unique
-- key, so a concurrent first-open race (two requests INSERTing between each
-- other's SELECT and INSERT) silently created duplicate rows -- after which
-- find_by_bookmark / find_or_create (.one()) 500'd with MultipleResultsFound.
--
-- The models now insert inside a SAVEPOINT and re-query on IntegrityError, which
-- only works once the constraint below actually exists. Mirrors the fix already
-- applied to article_level_summary_context (PR #698, commit 01520e6b).
--
-- Prod was verified duplicate-free for all six (bookmark_id, anchor_id) pairs on
-- 2026-08-13 (0 duplicate groups per table), so no de-dupe step is required and
-- the ALTERs below will not fail on existing data. If you run this against an
-- environment that might contain duplicates, dedupe first with the same
-- DELETE...JOIN(keep MIN(id)) pattern as 26-05-26-a--dedupe-and-unique-user-video.sql.
--
-- Note on cost: each ALTER rewrites the table to add the unique key. These join
-- tables are small, but prefer off-peak if any has grown large.

ALTER TABLE article_summary_context
    ADD UNIQUE KEY uq_asc_bookmark_article (bookmark_id, article_id);

ALTER TABLE article_fragment_context
    ADD UNIQUE KEY uq_afc_bookmark_fragment (bookmark_id, article_fragment_id);

ALTER TABLE article_title_context
    ADD UNIQUE KEY uq_atc_bookmark_article (bookmark_id, article_id);

ALTER TABLE video_title_context
    ADD UNIQUE KEY uq_vtc_bookmark_video (bookmark_id, video_id);

ALTER TABLE video_caption_context
    ADD UNIQUE KEY uq_vcc_bookmark_caption (bookmark_id, caption_id);

ALTER TABLE example_sentence_context
    ADD UNIQUE KEY uq_esc_bookmark_example (bookmark_id, example_sentence_id);
