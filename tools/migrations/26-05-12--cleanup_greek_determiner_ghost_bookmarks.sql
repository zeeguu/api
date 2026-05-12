-- Clean up ghost bookmarks where a Greek determiner was tapped and Azure's
-- word-aligner returned a multi-word noun-phrase translation. This is the
-- bug class fixed by api PR #605 / ADR-019 (Stanza DET+NOUN auto-MWE).
-- These rows are already hidden in the reader via web PR #1113, but they
-- still show up in users' vocab lists and are noise; this removes them.
--
-- Companion Germanic + Romance cleanup was already executed manually on
-- 2026-05-12 (440 rows). The Greek cleanup wasn't run with it because the
-- Greek characters got stripped during a copy-paste through the terminal.
-- Greek letters are typed directly here so they survive.
--
-- See docs/history/26-05-12--translation-disambiguation-and-auto-mwe.md.

-- Step 1: clear preferred_bookmark_id FK refs so the bookmark rows are deletable.
UPDATE user_word
SET preferred_bookmark_id = NULL
WHERE preferred_bookmark_id IN (
  SELECT bookmark_id FROM (
    SELECT b.id AS bookmark_id FROM bookmark b
    JOIN user_word uw ON b.user_word_id = uw.id
    JOIN meaning m    ON uw.meaning_id = m.id
    JOIN phrase op    ON m.origin_id = op.id
    JOIN phrase tp    ON m.translation_id = tp.id
    WHERE b.is_mwe = 0
      AND b.total_tokens = 1
      AND op.content_lower IN (
        'ο','η','το','οι','τα',
        'τον','την','τη','τους','τις',
        'του','της','των',
        'ένας','μία','μια','ένα','έναν','ενός','μιας','μίας'
      )
      AND tp.content LIKE '% %'
  ) AS ghost_ids
);

-- Step 2: pre-clean example_sentence_context FK (delete_bookmark endpoint
-- does the same in Python at bookmarks_and_words.py:266-268).
DELETE esc
FROM example_sentence_context esc
JOIN bookmark b   ON esc.bookmark_id = b.id
JOIN user_word uw ON b.user_word_id = uw.id
JOIN meaning m    ON uw.meaning_id = m.id
JOIN phrase op    ON m.origin_id = op.id
JOIN phrase tp    ON m.translation_id = tp.id
WHERE b.is_mwe = 0
  AND b.total_tokens = 1
  AND op.content_lower IN (
    'ο','η','το','οι','τα',
    'τον','την','τη','τους','τις',
    'του','της','των',
    'ένας','μία','μια','ένα','έναν','ενός','μιας','μίας'
  )
  AND tp.content LIKE '% %';

-- Step 3: delete the ghost bookmarks.
DELETE b
FROM bookmark b
JOIN user_word uw ON b.user_word_id = uw.id
JOIN meaning m    ON uw.meaning_id = m.id
JOIN phrase op    ON m.origin_id = op.id
JOIN phrase tp    ON m.translation_id = tp.id
WHERE b.is_mwe = 0
  AND b.total_tokens = 1
  AND op.content_lower IN (
    'ο','η','το','οι','τα',
    'τον','την','τη','τους','τις',
    'του','της','των',
    'ένας','μία','μια','ένα','έναν','ενός','μιας','μίας'
  )
  AND tp.content LIKE '% %';
