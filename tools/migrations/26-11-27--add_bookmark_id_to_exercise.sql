-- Which bookmark (sentence context) was shown to the learner during this
-- exercise, captured before any post-exercise context rotation. Lets us
-- measure how many distinct contexts a learner actually saw before a recall
-- test (and spot individual example sentences with high error rates).
--
-- Nullable column with no FK at the end of the table: an instant ALTER on
-- MySQL 8, and deleting a bookmark never blocks or erases the historical count.
-- NULL for historical rows and context-free sources (Match, audio lessons,
-- verbal flashcards).

ALTER TABLE exercise ADD COLUMN bookmark_id INT NULL;
