-- Backfill for 26-10-03-a: relabel existing bookmarks that were stamped
-- 'reading' only because that used to be the default.
--
-- Run ONLY AFTER every process runs code that knows the new values (api
-- containers, crawler, crons). Older code raises LookupError when it loads a
-- bookmark whose translation_source it doesn't recognise.

-- Backfill: example-sentence bookmarks.
UPDATE bookmark b
JOIN bookmark_context bc ON b.context_id = bc.id
JOIN context_type ct ON bc.context_type_id = ct.id
SET b.translation_source = 'generated_example'
WHERE ct.type = 'ExampleSentence'
  AND b.translation_source = 'reading';


-- Backfill: user-added words.
--
-- UserEditedText alone is not enough: update_bookmark also switches a real
-- reading look-up to UserEditedText when the learner edits its context. Those
-- keep their source_id (the article); user-added words never had one.
--
-- An edited example-sentence bookmark also ends up here (its context type was
-- switched too). Its origin can't be recovered, and 'user_added' is closer than
-- 'reading'.
UPDATE bookmark b
JOIN bookmark_context bc ON b.context_id = bc.id
JOIN context_type ct ON bc.context_type_id = ct.id
SET b.translation_source = 'user_added'
WHERE ct.type = 'UserEditedText'
  AND b.source_id IS NULL
  AND b.translation_source = 'reading';
