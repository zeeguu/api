-- bookmark.translation_source used to default to 'reading', so any code path
-- that forgot to set it was counted as a reading look-up. Two did:
--
--   * GET /alternative_sentences pre-creates a bookmark for each of up to 5
--     generated example sentences to warm the exercise swipe UI (since
--     2026-04-09, commit 4926b313). About two thirds of all 'reading' rows.
--   * /add_custom_word and /add_word_to_learning, where the learner types in a
--     word themselves.
--
-- They get their own values, and the column loses its default: the model now
-- requires every caller to say where a bookmark came from.

ALTER TABLE bookmark
MODIFY COLUMN translation_source
    ENUM('reading', 'exercise', 'article_preview', 'generated_example', 'user_added')
    DEFAULT NULL
    COMMENT 'Where the bookmark was created: reading (full article), exercise, article_preview (home page summaries), generated_example (pre-created for exercise example sentences), user_added (typed in by the learner)';

-- Existing rows are relabelled by 26-10-03-b, which must wait until all
-- running code knows the new values.
