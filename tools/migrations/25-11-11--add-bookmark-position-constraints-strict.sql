-- Migration: Add strict NOT NULL constraints to bookmark position fields
-- Date: 2025-11-11
--
-- This migration ensures that all bookmarks have valid position data (token_i, sentence_i, total_tokens).
-- This prevents the February 2025 issue where 1,203 bookmarks were created with NULL positions.
--
-- PREREQUISITES:
-- 1. Run the position fix script to backfill existing NULL values:
--    python -m tools.user_word_integrity._fix_multiword_bookmark_positions --fix
--
-- 2. Delete unvalidatable bookmarks (those where word cannot be found in context):
--    python -m tools.user_word_integrity._delete_unvalidatable_bookmarks --delete
--
-- 3. Verify no NULL values remain:
--    SELECT COUNT(*) FROM bookmark WHERE token_i IS NULL OR sentence_i IS NULL OR total_tokens IS NULL;
--
-- IMPORTANT: This migration will FAIL if there are any NULL values in the table.
-- This is intentional - it forces us to fix the data first before adding constraints.
--
-- NOTE: This migration does NOT add DEFAULT values. The application MUST always
-- provide explicit position data. The backend validation (validate_and_update_position)
-- ensures this happens correctly.

ALTER TABLE bookmark
  MODIFY COLUMN sentence_i INT(11) NOT NULL COMMENT 'Sentence index where the word appears (0-indexed)',
  MODIFY COLUMN token_i INT(11) NOT NULL COMMENT 'Token index within the sentence (0-indexed)',
  MODIFY COLUMN total_tokens INT(11) NOT NULL COMMENT 'Number of tokens this bookmark spans (1 for single word, >1 for phrases)';

-- Verification query (should return 0):
-- SELECT COUNT(*) FROM bookmark WHERE token_i IS NULL OR sentence_i IS NULL OR total_tokens IS NULL;
