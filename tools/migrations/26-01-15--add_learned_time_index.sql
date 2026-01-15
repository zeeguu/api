-- Add composite index on user_word for learned words queries
-- This significantly speeds up queries that filter by user_id and learned_time
-- Used by: User.learned_user_words(), User.total_learned_user_words()
CREATE INDEX idx_user_word_user_learned ON user_word (user_id, learned_time);
