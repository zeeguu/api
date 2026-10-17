"""
Reading evidence and the practice gate (ADR 032): a word the learner keeps
reading without a look-up stops being offered in exercises, for users with the
reading_gate feature. The model is the EuroCALL 2026 paper's, §4.2.
"""
from datetime import datetime, timedelta
from unittest import TestCase

from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.word_scheduling.reading_evidence import (
    ARTICLE,
    GATE_LOG_ODDS,
    LOOKUP_ELSEWHERE,
    LOOKUP_IN_READ_ARTICLE,
    replay,
    stemmer_for,
    update_reading_evidence,
)

db_session = db.session
T0 = datetime(2026, 1, 1)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


class ReplayTest(TestCase):
    """The paper's update rule, without a database."""

    def test_clean_encounters_follow_the_papers_curve(self):
        # §4.2: one clean encounter gives 0.62, three 0.79, five 0.89
        for n, expected in [(1, 0.62), (3, 0.79), (5, 0.89)]:
            events = [(at(i), ARTICLE, {"hund"}) for i in range(n)]
            self.assertAlmostEqual(replay(events)["hund"].p_known, expected, places=2)

    def test_a_lookup_in_the_article_nets_minus_beta(self):
        events = [(at(0), ARTICLE, {"hund"}), (at(0), LOOKUP_IN_READ_ARTICLE, "hund")]
        evidence = replay(events)["hund"]
        self.assertAlmostEqual(evidence.log_odds, 0.9 * 0.5 - 1.5)
        self.assertEqual(evidence.clean_encounters, 0)
        self.assertEqual(evidence.lookups, 1)

    def test_on_equal_times_the_article_comes_before_its_lookup(self):
        events = [(at(0), LOOKUP_IN_READ_ARTICLE, "hund"), (at(0), ARTICLE, {"hund"})]
        self.assertAlmostEqual(replay(events)["hund"].log_odds, 0.9 * 0.5 - 1.5)

    def test_eight_clean_articles_reopen_a_word_after_one_lookup(self):
        lookup = [(at(0), LOOKUP_ELSEWHERE, "hund")]
        seven = lookup + [(at(i), ARTICLE, {"hund"}) for i in range(1, 8)]
        eight = seven + [(at(8), ARTICLE, {"hund"})]
        self.assertLess(replay(seven)["hund"].log_odds, GATE_LOG_ODDS)
        self.assertGreaterEqual(replay(eight)["hund"].log_odds, GATE_LOG_ODDS)

    def test_a_well_read_word_needs_two_new_lookups_to_reopen(self):
        # "Conservative, not stubborn" (paper §8): one stray click on a word
        # read thirty times is likely a misclick; a second one is not.
        events = [(at(i), ARTICLE, {"aber"}) for i in range(30)]
        events.append((at(30), LOOKUP_ELSEWHERE, "aber"))
        self.assertGreaterEqual(replay(events)["aber"].log_odds, GATE_LOG_ODDS)
        events.append((at(31), LOOKUP_ELSEWHERE, "aber"))
        self.assertLess(replay(events)["aber"].log_odds, GATE_LOG_ODDS)

    def test_stemmer_merges_inflections_and_drops_apostrophes(self):
        reduce = stemmer_for("da")
        self.assertEqual(reduce("Hunden"), reduce("hund"))
        self.assertEqual(stemmer_for("fr")("l'"), "l")
        self.assertEqual(stemmer_for("xx")("Word"), "word")


class ReadingGateTest(ModelTestMixIn):

    @classmethod
    def setUpClass(cls):
        from zeeguu.core.test.conftest import get_shared_app, get_mock, init_fixtures_once

        cls.app = get_shared_app()
        get_mock()

        with cls.app.app_context():
            init_fixtures_once()

            gated_user = UserRule().user
            gated_user.is_dev = True  # the toggle starts out on for dev accounts
            db_session.add(gated_user)
            db_session.commit()
            cls._gated_user_id = gated_user.id
            cls._normal_user_id = UserRule().user.id

    @classmethod
    def tearDownClass(cls):
        from zeeguu.core.test.conftest import cleanup_tables

        with cls.app.app_context():
            db_session.close()
            cleanup_tables()

    def setUp(self):
        self.gated_user = User.find_by_id(self._gated_user_id)
        self.normal_user = User.find_by_id(self._normal_user_id)

    def tearDown(self):
        pass  # tables are cleaned once, in tearDownClass

    def run(self, result=None):
        with self.app.app_context():
            super(ModelTestMixIn, self).run(result)

    def _word(self, user, origin, looked_up_at):
        bookmark = BookmarkRule(user).bookmark
        bookmark.time = looked_up_at
        bookmark.user_word.meaning.origin.content = origin
        db_session.add(bookmark)
        db_session.commit()
        return bookmark.user_word

    def _read(self, user, content, start, duration_ms=60_000):
        article = ArticleRule().article
        article.content = content
        article.word_count = len(content.split())
        article.language = user.learned_language
        session = UserReadingSession(user.id, article.id, start)
        session.duration = duration_ms
        db_session.add_all([article, session])
        db_session.commit()

    def _update(self, user):
        changed = update_reading_evidence(db_session, user, user.learned_language)
        db_session.commit()
        return changed

    def test_toggle_is_on_only_for_dev_accounts(self):
        self.assertTrue(self.gated_user.has_feature("reading_gate"))
        self.assertFalse(self.normal_user.has_feature("reading_gate"))

    def test_word_read_cleanly_after_its_lookup_is_gated(self):
        user = self.gated_user
        word = self._word(user, "skovsnegl", looked_up_at=at(0))
        for i in range(1, 9):
            self._read(user, f"en skovsnegl i haven nummer {i}", at(i * 60))

        changed = self._update(user)

        self.assertTrue(word.known_from_reading)
        self.assertGreaterEqual(word.reading_log_odds, GATE_LOG_ODDS)
        self.assertIn(word, [uw for uw, _ in changed])

    def test_every_meaning_of_a_fluently_read_form_is_gated(self):
        # det = it / this / the: reading shows the form, not the meaning.
        # Three meanings are three look-ups, so it takes more reading.
        user = self.gated_user
        meanings = [self._word(user, "hejre", looked_up_at=at(0))]
        for _ in range(2):
            bookmark = BookmarkRule(user).bookmark
            bookmark.time = at(0)
            other = bookmark.user_word
            other.meaning.origin = meanings[0].meaning.origin  # same form, other translation
            db_session.add_all([bookmark, other])
            meanings.append(other)
        db_session.commit()
        for i in range(1, 21):
            self._read(user, f"en hejre ved søen nummer {i}", at(i * 60))

        self._update(user)

        self.assertTrue(all(uw.known_from_reading for uw in meanings))

    def test_too_little_reading_leaves_the_gate_open(self):
        user = self.gated_user
        word = self._word(user, "regnorm", looked_up_at=at(0))
        for i in range(1, 4):
            self._read(user, "en regnorm i haven", at(i * 60))

        self._update(user)

        self.assertFalse(word.known_from_reading)
        self.assertIsNotNone(word.reading_log_odds)

    def test_skimmed_articles_are_not_evidence(self):
        user = self.gated_user
        word = self._word(user, "pindsvin", looked_up_at=at(0))
        for i in range(1, 12):
            self._read(user, "et pindsvin i haven", at(i * 60), duration_ms=5_000)

        self._update(user)

        self.assertFalse(word.known_from_reading)
        self.assertAlmostEqual(word.reading_log_odds, -1.0)  # the look-up alone

    def test_a_word_the_learner_opted_into_is_never_gated(self):
        user = self.gated_user
        word = self._word(user, "mariehone", looked_up_at=at(0))
        word.user_preference = UserWordExPreference.USE_IN_EXERCISES
        for i in range(1, 12):
            self._read(user, "en mariehone i haven", at(i * 60))

        self._update(user)

        self.assertFalse(word.known_from_reading)

    def test_gated_words_leave_exercises_only_for_users_with_the_feature(self):
        gated = self._word(self.gated_user, "solsort", looked_up_at=at(0))
        not_gated = self._word(self.normal_user, "musvit", looked_up_at=at(0))
        for uw in (gated, not_gated):
            uw.known_from_reading = True
            db_session.add(uw)
        db_session.commit()

        self.assertNotIn(gated, BasicSRSchedule.user_words_to_study(self.gated_user))
        self.assertNotIn(gated, BasicSRSchedule.user_words_not_scheduled(self.gated_user, None))
        self.assertIn(not_gated, BasicSRSchedule.user_words_to_study(self.normal_user))
