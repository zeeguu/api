-- Migration: Add missing indexes for improved query performance
-- Date: 2025-10-03
-- Description: Adds indexes on frequently queried datetime, boolean, and sorting columns

-- Article indexes
ALTER TABLE article
    ADD INDEX idx_published_time (published_time);

-- Basic SR Schedule indexes (critical for spaced repetition)
ALTER TABLE basic_sr_schedule
    ADD INDEX idx_next_practice_time (next_practice_time);
ALTER TABLE basic_sr_schedule
    ADD INDEX idx_cooling_interval (cooling_interval);

-- Bookmark indexes
ALTER TABLE bookmark
    ADD INDEX idx_time (time);
ALTER TABLE bookmark
    ADD INDEX idx_starred (starred);

-- Exercise indexes
ALTER TABLE exercise
    ADD INDEX idx_time (time);

-- User Activity Data indexes
ALTER TABLE user_activity_data
    ADD INDEX idx_event (event);

-- User activity events by time
ALTER TABLE user_activity_data
    ADD INDEX idx_user_event_time (user_id, event, time);


-- User Article indexes (for filtering starred/liked/hidden articles)
ALTER TABLE user_article
    ADD INDEX idx_starred (starred);
ALTER TABLE user_article
    ADD INDEX idx_liked (liked);
ALTER TABLE user_article
    ADD INDEX idx_hidden (hidden);

-- User Reading Session indexes
ALTER TABLE user_reading_session
    ADD INDEX idx_start_time (start_time);
ALTER TABLE user_reading_session
    ADD INDEX idx_is_active (is_active);

-- User Exercise Session indexes
ALTER TABLE user_exercise_session
    ADD INDEX idx_start_time (start_time);
ALTER TABLE user_exercise_session
    ADD INDEX idx_is_active (is_active);

-- Composite indexes for common query patterns
-- User reading history sorted by time
ALTER TABLE user_reading_session
    ADD INDEX idx_user_start_time (user_id, start_time);


-- Exercise history for a word
ALTER TABLE exercise
    ADD INDEX idx_user_word_time (user_word_id, time);

-- Bookmark history for a user word
ALTER TABLE bookmark
    ADD INDEX idx_user_word_time (user_word_id, time);

-- Articles by language and publish date (for feed queries)
ALTER TABLE article
    ADD INDEX idx_language_published (language_id, published_time);

-- Practice scheduling (most critical for performance)
ALTER TABLE basic_sr_schedule
    ADD INDEX idx_user_word_next_practice (user_word_id, next_practice_time);
