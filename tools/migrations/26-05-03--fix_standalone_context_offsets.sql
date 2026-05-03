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

UPDATE bookmark_context bc
JOIN context_type ct ON bc.context_type_id = ct.id
SET
  bc.token_i = 0,
  bc.sentence_i = 0,
  bc.cached_tokenized = NULL
WHERE ct.type IN ('UserEditedText', 'ExampleSentence')
  AND (bc.token_i > 0 OR bc.sentence_i > 0);
