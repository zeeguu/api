-- Add composite index to optimize find_all_for_context_and_user query
-- This query is called during bookmark quality checks and can be slow
-- when a context has many bookmarks (e.g., article titles, common phrases)

CREATE INDEX idx_bookmark_context_user_word ON bookmark(context_id, user_word_id);
