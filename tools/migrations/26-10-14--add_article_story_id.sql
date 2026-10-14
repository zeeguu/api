-- Groups articles that report the same story (same event, different outlet or
-- a republished update) so the feed can show one card per story. Holds the id
-- of the first article of the story; NULL means the article is its own story.
-- Deliberately no FK: the nightly pruning deletes old articles, and a story id
-- pointing at a pruned article is still a valid grouping key.
ALTER TABLE article
    ADD COLUMN story_id INT NULL DEFAULT NULL,
    ADD INDEX article_story_id (story_id);
