-- Standalone-sentence context types (UserEditedText from the translate tab,
-- ExampleSentence from /alternative_sentences) had bookmark_context.token_i
-- and sentence_i wrongly set to the *target word's* position instead of the
-- context's first-token offset (0). See word_position_finder.py — both
-- validate_single_occurrence and find_first_occurrence used to return
-- c_token_i = position['token_i'].
--
-- Downstream, BookmarkContext.get_tokenized() uses self.token_i as
-- start_token_i for the Stanza tokenizer, which then numbered the FIRST
-- token of the cached span with the target's index. The frontend's
-- WordInContext highlight then matched the wrong word (e.g. "At lære"
-- instead of "tålmodighed").
--
-- Reset offsets to 0 and drop the cache so it regenerates correctly on
-- next access.

-- Snapshot the affected rows so rollback is a single statement away.
DROP TABLE IF EXISTS _bc_offset_fix_backup_26_05_03;
CREATE TABLE _bc_offset_fix_backup_26_05_03 AS
SELECT bc.id, bc.sentence_i, bc.token_i, bc.cached_tokenized
FROM bookmark_context bc
JOIN context_type ct ON bc.context_type_id = ct.id
WHERE ct.type IN ('UserEditedText', 'ExampleSentence')
  AND (bc.token_i > 0 OR bc.sentence_i > 0);

-- Sanity check: should be ~5,701.
SELECT COUNT(*) AS rows_to_fix FROM _bc_offset_fix_backup_26_05_03;

-- Apply the fix.
UPDATE bookmark_context bc
JOIN context_type ct ON bc.context_type_id = ct.id
SET
  bc.token_i = 0,
  bc.sentence_i = 0,
  bc.cached_tokenized = NULL
WHERE ct.type IN ('UserEditedText', 'ExampleSentence')
  AND (bc.token_i > 0 OR bc.sentence_i > 0);

-- Verify: should be 0.
SELECT COUNT(*) AS still_broken
FROM bookmark_context bc
JOIN context_type ct ON bc.context_type_id = ct.id
WHERE ct.type IN ('UserEditedText', 'ExampleSentence')
  AND (bc.token_i > 0 OR bc.sentence_i > 0);

-- Rollback (if needed):
-- UPDATE bookmark_context bc
-- JOIN _bc_offset_fix_backup_26_05_03 b ON bc.id = b.id
-- SET bc.sentence_i = b.sentence_i, bc.token_i = b.token_i, bc.cached_tokenized = b.cached_tokenized;
