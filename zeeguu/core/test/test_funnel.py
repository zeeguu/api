"""Tests for the demand-aware ingestion funnel (Task 5).

The quota / budget / floor logic is pure Python and tested without a DB. The
demand-surface query is tested against real User + TopicSubscription rows.
"""

import datetime
from unittest import TestCase

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.topic_rule import TopicRule

from zeeguu.core.content_retriever.funnel import (
    DemandSurface,
    FunnelBudget,
    compute_demand_surface,
    triage_keep_count,
    select_titles_to_download,
    _active_quota,
    MIN_ACTIVE_QUOTA,
    MAX_ACTIVE_QUOTA,
    LANGUAGE_FLOOR_TOPICS,
    TRIAGE_OVERSHOOT,
)

db_session = zeeguu.core.model.db.session


class FunnelQuotaTest(TestCase):
    """Pure quota-scaling logic; no DB needed."""

    def test_single_reader_gets_min_quota(self):
        self.assertEqual(_active_quota(1), MIN_ACTIVE_QUOTA)

    def test_quota_scales_up_with_readers(self):
        self.assertEqual(_active_quota(1), 20)
        self.assertEqual(_active_quota(5), 20)
        self.assertEqual(_active_quota(6), 30)
        self.assertEqual(_active_quota(11), 40)
        self.assertEqual(_active_quota(16), 50)

    def test_quota_is_clamped_at_max(self):
        self.assertEqual(_active_quota(1000), MAX_ACTIVE_QUOTA)


class DemandSurfaceLogicTest(TestCase):
    """readers_for / language_has_demand; no DB needed."""

    def setUp(self):
        # Language 1: 2 readers subscribed to topic 10, plus 3 all-topic readers.
        # Language 2: only subscribed readers. Language 3: nothing.
        self.surface = DemandSurface(
            subscribed_readers={(1, 10): 2, (2, 20): 1},
            unfiltered_readers={1: 3},
        )

    def test_all_topic_readers_lend_demand_to_every_topic(self):
        # Topic 10 in lang 1: 2 subscribers + 3 all-topic = 5
        self.assertEqual(self.surface.readers_for(1, 10), 5)
        # An unsubscribed topic in lang 1 still has the 3 all-topic readers
        self.assertEqual(self.surface.readers_for(1, 99), 3)

    def test_subscribed_only_language(self):
        self.assertEqual(self.surface.readers_for(2, 20), 1)
        self.assertEqual(self.surface.readers_for(2, 99), 0)

    def test_language_has_demand(self):
        self.assertTrue(self.surface.language_has_demand(1))
        self.assertTrue(self.surface.language_has_demand(2))
        self.assertFalse(self.surface.language_has_demand(3))


class FunnelBudgetGateTest(TestCase):
    """should_simplify / record / floor diversity; no DB needed."""

    def test_demand_bucket_simplifies_until_quota(self):
        surface = DemandSurface({(1, 10): 1}, {})  # 1 reader -> quota 20
        budget = FunnelBudget(surface)
        for _ in range(MIN_ACTIVE_QUOTA):
            ok, reason = budget.should_simplify(1, [10])
            self.assertTrue(ok)
            self.assertEqual(reason, "demand")
            budget.record(1, [10], reason)
        ok, reason = budget.should_simplify(1, [10])
        self.assertFalse(ok)
        self.assertEqual(reason, "capped")

    def test_seeded_counts_are_respected(self):
        surface = DemandSurface({(1, 10): 1}, {})
        budget = FunnelBudget(surface, todays_counts={(1, 10): MIN_ACTIVE_QUOTA})
        ok, reason = budget.should_simplify(1, [10])
        self.assertFalse(ok)

    def test_article_matches_if_any_topic_under_quota(self):
        # Topic 10 full, topic 11 has demand and room -> simplify.
        surface = DemandSurface({(1, 10): 1, (1, 11): 1}, {})
        budget = FunnelBudget(surface, todays_counts={(1, 10): MIN_ACTIVE_QUOTA})
        ok, reason = budget.should_simplify(1, [10, 11])
        self.assertTrue(ok)
        self.assertEqual(reason, "demand")

    def test_no_topics_skipped_without_all_topic_readers(self):
        # Topic-subscribers can never see an untagged article, so skip it.
        budget = FunnelBudget(DemandSurface({(1, 10): 1}, {}))
        ok, reason = budget.should_simplify(1, [])
        self.assertFalse(ok)
        self.assertEqual(reason, "no-topics")

    def test_no_topics_simplified_for_all_topic_readers(self):
        # A reader with no subscription reads the whole language, untagged included.
        budget = FunnelBudget(DemandSurface({}, {1: 2}))
        ok, reason = budget.should_simplify(1, [])
        self.assertTrue(ok)
        self.assertEqual(reason, "no-topic")

    def test_dormant_language_gets_topic_diverse_floor(self):
        # No demand anywhere -> language 1 is dormant; floor keeps a few distinct
        # topics warm, one each, capped at LANGUAGE_FLOOR_TOPICS.
        budget = FunnelBudget(DemandSurface({}, {}))
        simplified_topics = []
        for topic_id in range(100, 100 + LANGUAGE_FLOOR_TOPICS + 3):
            ok, reason = budget.should_simplify(1, [topic_id])
            if ok:
                self.assertEqual(reason, "floor")
                budget.record(1, [topic_id], reason)
                simplified_topics.append(topic_id)
        self.assertEqual(len(simplified_topics), LANGUAGE_FLOOR_TOPICS)

    def test_floor_does_not_refire_same_topic(self):
        budget = FunnelBudget(DemandSurface({}, {}))
        ok, reason = budget.should_simplify(1, [100])
        self.assertTrue(ok)
        budget.record(1, [100], reason)
        # Same topic again: floor is 1/topic, so no more.
        ok, _ = budget.should_simplify(1, [100])
        self.assertFalse(ok)

    def test_language_with_demand_gets_no_floor(self):
        # Lang 1 has demand on topic 10; a different, unsubscribed topic 99 with
        # 0 readers gets neither demand nor floor (floor is only for dormant langs).
        surface = DemandSurface({(1, 10): 1}, {})
        budget = FunnelBudget(surface)
        ok, reason = budget.should_simplify(1, [99])
        self.assertFalse(ok)
        self.assertEqual(reason, "capped")


class HeadroomTest(TestCase):
    """language_simplification_headroom drives the pre-download triage; no DB."""

    def test_all_topic_readers_mean_unbounded(self):
        budget = FunnelBudget(DemandSurface({}, {1: 3}))
        self.assertIsNone(budget.language_simplification_headroom(1))

    def test_dormant_language_headroom_is_floor_slots_left(self):
        budget = FunnelBudget(DemandSurface({}, {}))
        self.assertEqual(
            budget.language_simplification_headroom(1), LANGUAGE_FLOOR_TOPICS
        )
        budget.record(1, [100], "floor")
        self.assertEqual(
            budget.language_simplification_headroom(1), LANGUAGE_FLOOR_TOPICS - 1
        )

    def test_subscribed_language_headroom_sums_remaining_quota(self):
        # Two demanded buckets, quota 20 each. One already half used.
        surface = DemandSurface({(1, 10): 1, (1, 11): 1}, {})
        budget = FunnelBudget(surface, todays_counts={(1, 10): 5})
        self.assertEqual(
            budget.language_simplification_headroom(1),
            (MIN_ACTIVE_QUOTA - 5) + MIN_ACTIVE_QUOTA,
        )

    def test_fully_used_language_has_zero_headroom(self):
        surface = DemandSurface({(1, 10): 1}, {})
        budget = FunnelBudget(surface, todays_counts={(1, 10): MIN_ACTIVE_QUOTA})
        self.assertEqual(budget.language_simplification_headroom(1), 0)


class TriageSelectionTest(TestCase):
    """triage_keep_count + select_titles_to_download; no DB."""

    def test_keep_count_unbounded_uses_limit(self):
        self.assertEqual(triage_keep_count(None, 10), 10)

    def test_keep_count_zero_headroom_skips(self):
        self.assertEqual(triage_keep_count(0, 10), 0)

    def test_keep_count_overshoots_but_respects_limit(self):
        self.assertEqual(triage_keep_count(2, 10), 2 * TRIAGE_OVERSHOOT)
        self.assertEqual(triage_keep_count(50, 10), 10)

    def test_keep_all_when_fewer_titles_than_keep(self):
        titles = ["a", "b"]
        self.assertEqual(select_titles_to_download(titles, "de", [], 5), [0, 1])

    def test_ranker_choice_is_honoured(self):
        titles = ["a", "b", "c", "d"]

        def ranker(ts, lang, interests, keep):
            return [3, 1]

        self.assertEqual(
            select_titles_to_download(titles, "de", [], 2, ranker=ranker), [3, 1]
        )

    def test_ranker_output_is_sanitized(self):
        titles = ["a", "b", "c", "d"]

        def messy_ranker(ts, lang, interests, keep):
            return [3, 3, 99, "x", 1]  # dupes, out-of-range, wrong type

        self.assertEqual(
            select_titles_to_download(titles, "de", [], 3, ranker=messy_ranker), [3, 1]
        )

    def test_ranker_failure_falls_back_to_first_n(self):
        titles = ["a", "b", "c", "d"]

        def broken_ranker(ts, lang, interests, keep):
            raise RuntimeError("LLM down")

        self.assertEqual(
            select_titles_to_download(titles, "de", [], 2, ranker=broken_ranker), [0, 1]
        )

    def test_empty_ranker_output_falls_back_to_first_n(self):
        titles = ["a", "b", "c", "d"]
        self.assertEqual(
            select_titles_to_download(titles, "de", [], 2, ranker=lambda *a: []),
            [0, 1],
        )


class ComputeDemandSurfaceTest(ModelTestMixIn, TestCase):
    """The demand-surface query against real User + TopicSubscription rows."""

    def setUp(self):
        super().setUp()
        from zeeguu.core.model.topic_subscription import TopicSubscription

        self.lang = LanguageRule().de
        self.topic_sports = TopicRule.get_or_create_topic(1)
        self.topic_tech = TopicRule.get_or_create_topic(3)

        # Active subscribed reader: German, subscribed to Sports.
        self.subscribed = UserRule().user
        self.subscribed.learned_language = self.lang
        self.subscribed.last_seen = datetime.datetime.now()
        TopicSubscription.find_or_create(db_session, self.subscribed, self.topic_sports)

        # Active all-topic reader: German, no subscriptions.
        self.unfiltered = UserRule().user
        self.unfiltered.learned_language = self.lang
        self.unfiltered.last_seen = datetime.datetime.now()

        # Dormant reader: German, but not seen in a long time -> excluded.
        self.dormant = UserRule().user
        self.dormant.learned_language = self.lang
        self.dormant.last_seen = datetime.datetime.now() - datetime.timedelta(days=90)
        TopicSubscription.find_or_create(db_session, self.dormant, self.topic_tech)

        db_session.commit()

    def test_active_subscribers_and_all_topic_readers_counted(self):
        surface = compute_demand_surface(db_session)
        # Sports: 1 subscriber + 1 all-topic reader = 2
        self.assertEqual(surface.readers_for(self.lang.id, self.topic_sports.id), 2)
        # Tech: subscribed only by the dormant reader (excluded), but the
        # all-topic active reader still lends demand = 1
        self.assertEqual(surface.readers_for(self.lang.id, self.topic_tech.id), 1)
        self.assertTrue(surface.language_has_demand(self.lang.id))

    def test_dormant_reader_excluded(self):
        # If we shrink the active window below the dormant reader's staleness it
        # stays excluded; the all-topic reader alone keeps tech demand at 1, not 2.
        surface = compute_demand_surface(db_session)
        self.assertEqual(surface.readers_for(self.lang.id, self.topic_tech.id), 1)


class BackfillInventoryTest(ModelTestMixIn, TestCase):
    """fresh_simplified_count / recent_unsimplified_articles against real rows."""

    def setUp(self):
        super().setUp()
        from zeeguu.core.test.rules.article_rule import ArticleRule
        from zeeguu.core.model import ArticleTopicMap
        from zeeguu.core.model.article_topic_map import TopicOriginType

        self.lang = LanguageRule().de
        self.topic = TopicRule.get_or_create_topic(1)  # Sports

        def make_original(days_old, broken=0):
            art = ArticleRule().article
            art.language = self.lang
            art.parent_article_id = None
            art.broken = broken
            art.published_time = datetime.datetime.now() - datetime.timedelta(days=days_old)
            db_session.add(
                ArticleTopicMap(art, self.topic, TopicOriginType.HARDSET)
            )
            db_session.commit()
            return art

        # Two fresh raw originals with the topic, not yet simplified.
        self.raw_recent = [make_original(1), make_original(2)]
        # One old raw original (outside the lookback window).
        self.raw_old = make_original(30)

        # One original that HAS a simplified child (so it's "fresh simplified").
        self.parent = make_original(1)
        child = ArticleRule().article
        child.language = self.lang
        child.parent_article_id = self.parent.id
        child.broken = 0
        child.published_time = datetime.datetime.now()
        db_session.add(child)
        db_session.commit()

    def test_fresh_simplified_count_counts_children_in_window(self):
        from zeeguu.core.content_retriever.backfill import fresh_simplified_count

        self.assertEqual(
            fresh_simplified_count(db_session, self.lang.id, self.topic.id), 1
        )

    def test_recent_unsimplified_excludes_old_and_already_simplified(self):
        from zeeguu.core.content_retriever.backfill import recent_unsimplified_articles

        found = recent_unsimplified_articles(db_session, self.lang.id, self.topic.id)
        found_ids = {a.id for a in found}
        # The two fresh raw originals are eligible...
        for art in self.raw_recent:
            self.assertIn(art.id, found_ids)
        # ...but the old one and the already-simplified parent are not.
        self.assertNotIn(self.raw_old.id, found_ids)
        self.assertNotIn(self.parent.id, found_ids)

    def test_recent_unsimplified_respects_topic_filter(self):
        from zeeguu.core.content_retriever.backfill import recent_unsimplified_articles

        other_topic = TopicRule.get_or_create_topic(7)  # Politics — nothing tagged
        found = recent_unsimplified_articles(db_session, self.lang.id, other_topic.id)
        self.assertEqual(found, [])
