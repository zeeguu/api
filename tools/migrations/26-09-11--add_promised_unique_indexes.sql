-- Five unique keys the models have declared for years and production never had.
--
-- Found by comparing the live production index list against what SQLAlchemy
-- puts on db.metadata (the sweep in #741, run backwards). Because the test
-- database is built by db.create_all() from the models, each of these has been
-- enforced in tests and unenforced in production -- the reverse of the #741
-- problem, and the reason a race that tests refuse can duplicate rows in prod.
--
-- Production data was checked first: all five have ZERO duplicate groups today,
-- so every ALTER below can be applied as-is with no dedupe step.
--
-- level_adapted_article_summary_context is the clearest case: its sibling
-- level_adapted_article_title_context has uq_latc_bookmark_title in production,
-- and this one was almost certainly lost when article_level_summary was renamed
-- and the column became level_adapted_article_text_id. Its find_or_create
-- already inserts inside a SAVEPOINT expecting the constraint to be there.
--
-- The other four had find_or_create methods that caught only NoResultFound and
-- would have turned a lost race into a 500 once the key existed; they now use
-- the same SAVEPOINT-and-requery pattern as UserLanguage.find_or_create (#733).
-- Apply this migration together with that code change, not ahead of it.
--
-- Cost: none of these tables is large and each already has an index on the
-- leading column, so the ALTERs are quick. Still prefer off-peak.

ALTER TABLE level_adapted_article_summary_context
    ADD UNIQUE KEY uq_alsc_bookmark_summary (bookmark_id, level_adapted_article_text_id);

ALTER TABLE search_filter
    ADD UNIQUE KEY uq_search_filter_user_search (user_id, search_id);

ALTER TABLE search_subscription
    ADD UNIQUE KEY uq_search_subscription_user_search (user_id, search_id);

ALTER TABLE topic_filter
    ADD UNIQUE KEY uq_topic_filter_user_topic (user_id, topic_id);

ALTER TABLE topic_subscription
    ADD UNIQUE KEY uq_topic_subscription_user_topic (user_id, topic_id);
