/*
  Let a bookmark's context join rows be deleted with the bookmark.

  Symptom
  -------
  ~25 unhandled MySQLdb.IntegrityError (1451) "Cannot delete or update a parent
  row" between Sep 2 and Sep 11 2026, every one of them a DELETE on `bookmark`
  blocked by a join table that still referenced it. Users got a 500 from
  /delete_bookmark and, because the client leaves the delete dialog open on
  failure, retried -- one session hit the same bookmark three times in 18s.

  Root cause
  ----------
  Six of the bookmark-context join tables are ON DELETE CASCADE; four are not:

      article_fragment_context               CASCADE
      article_summary_context                CASCADE
      article_title_context                  CASCADE
      video_caption_context                  CASCADE
      video_title_context                    CASCADE
      bookmark_translation_mapping           CASCADE
      example_sentence_context               RESTRICT   <-- fixed below
      level_adapted_article_summary_context  RESTRICT   <-- fixed below
      level_adapted_article_title_context    RESTRICT   <-- fixed below
      exercise_report                        RESTRICT   <-- fixed below

  The two level_adapted_* FKs are a plain omission: 26-08-12 gave fk_alsc_summary
  a cascade but not fk_alsc_bookmark, and 26-08-28 copied that asymmetry into
  fk_latc_bookmark. They started firing on Sep 2, days after per-level titles
  shipped and readers began tapping words in them.

  example_sentence_context is different: it is SCHEMA DRIFT. 25-07-31 creates it
  with ON DELETE CASCADE and names the constraint example_sentence_context_
  bookmark_FK; prod has example_sentence_context_ibfk_1 and RESTRICT. That is the
  signature of db.create_all() (zeeguu/api/app.py) having built the table from the
  model -- and the models declare no ondelete at all. Same for its sibling
  example_sentence, whose meaning_id FK is RESTRICT in prod where the migration
  says CASCADE. This migration ships alongside a model change adding
  ondelete="CASCADE" to every bookmark FK, so create_all and the migrations stop
  disagreeing.

  NOT changed here, on purpose:
    - example_sentence_context_ibfk_2 (-> example_sentence) and
      example_sentence.meaning_id (-> meaning) are also RESTRICT-where-the-
      migration-said-CASCADE. Nothing in the codebase deletes a meaning, and
      tools/validate_and_clean_examples.py deliberately REFUSES to delete an
      example that a bookmark still links to rather than taking the user's
      context row with it. Cascading those is a product decision, not a bug fix.

  Why CASCADE and not "delete the children in Python first"
  ---------------------------------------------------------
  Because the children are pure anchors: a context row records WHERE in a text a
  bookmark was found. With no bookmark it means nothing, so there is never a
  reason to keep one. delete_bookmark already hand-deletes ExampleSentenceContext
  rows (commit f8a6cd21, Jan 2026) for exactly this reason -- but it is one of
  four code paths that delete bookmarks, and the other three inherited nothing.
  The fourth is not even obviously a bookmark delete: the LLM translation
  validator orphans a UserWord, and bookmark.user_word_id is ON DELETE CASCADE
  (25-05-24), so MySQL walks into these join tables on its own. No amount of
  Python-side bookkeeping catches a cascade the database initiates.

  exercise_report deserves its own sentence: bookmark_id is NOT NULL, so SET NULL
  is unavailable, and cascading means a user's "this exercise is broken" report
  dies with the bookmark it describes. That matches what
  user_account_deletion.py already does (it deletes exercise_report rows along
  with the bookmarks). 34 rows in the table today; it has never actually blocked
  a delete, which is luck rather than design.

  Safety
  ------
  Verified on prod 2026-09-11: zero orphaned bookmark_id values in all four
  tables, so re-adding each FK validates cleanly. Row counts are small --
  example_sentence_context 39,962, level_adapted_article_summary_context 294,
  level_adapted_article_title_context 140, exercise_report 34 -- so the table
  rebuilds are quick. No off-peak window needed.

  NOTE: MySQL rejects dropping and re-adding a FK of the same name in one ALTER
  (error 1826 "duplicate foreign key constraint name"), so each table uses two
  statements: DROP then ADD. The DROP keeps the underlying index, so the ADD
  reuses it.

  NOTE: the example_sentence_context constraint is named _ibfk_1 because prod got
  the table from create_all. An environment that DID apply 25-07-31 has it as
  example_sentence_context_bookmark_FK and already cascades -- check before
  running:
      SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE
      FROM information_schema.REFERENTIAL_CONSTRAINTS
      WHERE CONSTRAINT_SCHEMA = DATABASE()
        AND REFERENCED_TABLE_NAME = 'bookmark';
*/

ALTER TABLE level_adapted_article_title_context DROP FOREIGN KEY fk_latc_bookmark;
ALTER TABLE level_adapted_article_title_context
    ADD CONSTRAINT fk_latc_bookmark FOREIGN KEY (bookmark_id)
        REFERENCES bookmark (id) ON DELETE CASCADE;

ALTER TABLE level_adapted_article_summary_context DROP FOREIGN KEY fk_alsc_bookmark;
ALTER TABLE level_adapted_article_summary_context
    ADD CONSTRAINT fk_alsc_bookmark FOREIGN KEY (bookmark_id)
        REFERENCES bookmark (id) ON DELETE CASCADE;

-- Renamed to the spelling 25-07-31 intended, so the next person comparing the
-- migration to the live schema sees a match instead of this drift again.
ALTER TABLE example_sentence_context DROP FOREIGN KEY example_sentence_context_ibfk_1;
ALTER TABLE example_sentence_context
    ADD CONSTRAINT example_sentence_context_bookmark_FK FOREIGN KEY (bookmark_id)
        REFERENCES bookmark (id) ON DELETE CASCADE;

ALTER TABLE exercise_report DROP FOREIGN KEY exercise_report_ibfk_2;
ALTER TABLE exercise_report
    ADD CONSTRAINT exercise_report_bookmark_FK FOREIGN KEY (bookmark_id)
        REFERENCES bookmark (id) ON DELETE CASCADE;
