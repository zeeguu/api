/*
  Make the article-pruning safe by letting foreign keys protect data we keep.

  Background
  ----------
  prune_old_articles.py (and anonymize_users.py) used to delete articles with
  FOREIGN_KEY_CHECKS=0 and manually re-implement the cascade. That is fragile
  (a lost session setting crashed a real run mid-way) and, worse, it silently
  CASCADE-deleted data we actually want to keep.

  The fix is to prune with FK checks ON and let the schema express intent:
    - derived/regenerable children (article_fragment, *_tokenization_cache,
      cefr/classification/topic/url_keyword/difficulty/grammar_log, ...) stay
      ON DELETE CASCADE  -> deleted automatically with the article.
    - parent_article_id stays ON DELETE CASCADE: pruning an original takes its
      unreferenced simplifications with it. To avoid cascade-deleting (or
      blocking on) a simplification that is still referenced, prune protects the
      original itself whenever any of its simplifications is referenced (see
      referenced_article_ids in prune_old_articles.py) -- so the family stays
      together and no simplification is ever orphaned.
    - tables we want to PRESERVE must BLOCK an article's deletion instead of
      being cascade-deleted. They are switched to ON DELETE RESTRICT below.
    - user_article / user_reading_session / text and the bookmark-context
      tables are already NO ACTION, so they already block. No change needed.

  After this migration, prune deletes with FK checks ON and simply skips any
  article whose deletion is blocked -- so a still-referenced article is never
  force-deleted, and the data below is never silently lost.

  NOTE: re-adding each FK validates existing rows. user_activity_data is large;
  expect the ALTER to take a while and hold a metadata lock. Run during low
  traffic. Each table currently has zero orphaned article_id values, so
  validation will pass.
*/

-- NOTE: MySQL rejects dropping and re-adding a FK of the same name in one
-- ALTER (error 1826 "duplicate foreign key constraint name"), so each table
-- uses two statements: DROP then ADD. The DROP keeps the underlying index, so
-- the ADD reuses it.

ALTER TABLE personal_copy DROP FOREIGN KEY personal_copy_ibfk_2;
ALTER TABLE personal_copy ADD CONSTRAINT personal_copy_ibfk_2
  FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE RESTRICT;

ALTER TABLE user_activity_data DROP FOREIGN KEY user_activity_data_ibfk_2;
ALTER TABLE user_activity_data ADD CONSTRAINT user_activity_data_ibfk_2
  FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE RESTRICT;

ALTER TABLE cohort_article_map DROP FOREIGN KEY cohort_article_map_ibfk_2;
ALTER TABLE cohort_article_map ADD CONSTRAINT cohort_article_map_ibfk_2
  FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE RESTRICT;

ALTER TABLE article_topic_user_feedback DROP FOREIGN KEY article_topic_user_feedback_ibfk_1;
ALTER TABLE article_topic_user_feedback ADD CONSTRAINT article_topic_user_feedback_ibfk_1
  FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE RESTRICT;

ALTER TABLE user_article_broken_report DROP FOREIGN KEY fk_user_broken_report_article;
ALTER TABLE user_article_broken_report ADD CONSTRAINT fk_user_broken_report_article
  FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE RESTRICT;

-- parent_article_id is intentionally left ON DELETE CASCADE (see header):
-- prune protects an original whose simplification is referenced, so the only
-- simplifications that ever cascade are unreferenced ones.
