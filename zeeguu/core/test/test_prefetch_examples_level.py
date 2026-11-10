"""The nightly example prefetch covers the words the exercises will show next,
at the learner's level. An A2 learner's new words used to have no examples,
or B1-C2 ones (user 6885, 9 Nov 2026)."""

from datetime import datetime, timedelta
from unittest import TestCase

import zeeguu.core
from tools.prefetch_example_sentences_for_users import (
    forget_tries_of_covered_meanings,
    get_user_words_needing_examples,
    intended_generator,
)
from zeeguu.core.model import ExampleGenerationAttempt, UserLanguage
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.util.time import server_now

session = zeeguu.core.model.db.session


class PrefetchAtLearnerLevelTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = self._learner(level=2)  # A2
        self.user_word = BookmarkRule(self.user).bookmark.user_word
        self.user_word.fit_for_study = True
        session.commit()

    def _learner(self, level):
        user = UserRule().user
        user.last_seen = datetime.now()
        user_language = UserLanguage.find_or_create(session, user, user.learned_language)
        user_language.cefr_level = level
        session.commit()
        return user

    def _examples(self, *levels):
        for i, level in enumerate(levels):
            session.add(
                ExampleSentence(f"sentence {i} {level}", self.user.learned_language, self.user_word.meaning, cefr_level=level)
            )
        session.commit()

    def _needing(self, user=None):
        return [(uw.id, level) for uw, level in get_user_words_needing_examples(user)]

    def test_a_new_word_without_examples_is_covered_at_the_learners_level(self):
        self.assertIn((self.user_word.id, "A2"), self._needing(self.user))

    def test_examples_above_the_learners_level_do_not_count(self):
        self._examples("B1", "B2", "C2")
        self.assertIn((self.user_word.id, "A2"), self._needing(self.user))

    def test_enough_easier_examples_cover_the_word(self):
        self._examples("A1", "A2", "A2")
        self.assertNotIn((self.user_word.id, "A2"), self._needing(self.user))

    def test_a_meaning_shared_at_one_level_comes_once(self):
        other = self._learner(level=2)
        # Same language, or the scheduler's language filter hides the word
        # and the test passes without any dedup
        other.learned_language = self.user.learned_language
        session.commit()
        other_word = BookmarkRule(other).bookmark.user_word
        other_word.meaning = self.user_word.meaning
        other_word.fit_for_study = True
        session.commit()

        needing = get_user_words_needing_examples()
        meanings = [(uw.meaning_id, level) for uw, level in needing]
        self.assertEqual(meanings.count((self.user_word.meaning_id, "A2")), 1)


    def test_the_most_recently_active_learner_comes_first(self):
        from datetime import timedelta

        self.user.last_seen = datetime.now() - timedelta(days=3)
        recent = self._learner(level=2)  # last_seen: now
        recent_word = BookmarkRule(recent).bookmark.user_word
        recent_word.fit_for_study = True
        session.commit()

        users_in_order = [uw.user_id for uw, _ in get_user_words_needing_examples()]
        self.assertLess(users_in_order.index(recent.id), users_in_order.index(self.user.id))

    def test_the_list_stops_at_the_limit(self):
        other = self._learner(level=2)
        other_word = BookmarkRule(other).bookmark.user_word
        other_word.fit_for_study = True
        session.commit()

        self.assertEqual(len(get_user_words_needing_examples(limit=1)), 1)


class TriesPauseTest(ModelTestMixIn, TestCase):
    """A meaning the LLM's sentences cannot be anchored for ("schreibt
    darüber"), or whose examples the validator rejects, would otherwise go to
    the LLM every night."""

    MODEL, PROMPT = "fake-model", "v4"

    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.user.last_seen = datetime.now()
        user_language = UserLanguage.find_or_create(session, self.user, self.user.learned_language)
        user_language.cefr_level = 2  # A2
        self.user_word = BookmarkRule(self.user).bookmark.user_word
        self.user_word.fit_for_study = True
        session.commit()
        self.meaning_id = self.user_word.meaning_id

    def _try(self, when, model=MODEL, prompt=PROMPT):
        generator = AIGenerator.find_or_create(session, model, prompt)
        ExampleGenerationAttempt.record_try(session, self.meaning_id, "A2", generator, now=when)
        session.commit()

    def _paused(self, now, key=(MODEL, PROMPT)):
        return self.meaning_id in ExampleGenerationAttempt.paused_meaning_ids({self.meaning_id}, "A2", key, now)

    def _listed(self, **kwargs):
        return self.user_word.id in [uw.id for uw, _ in get_user_words_needing_examples(self.user, **kwargs)]

    def _rows(self):
        return ExampleGenerationAttempt.query.filter_by(meaning_id=self.meaning_id).count()

    def test_a_week_after_the_first_try_a_month_after_the_second_then_for_good(self):
        start = datetime(2026, 11, 10)
        self._try(start)
        self.assertTrue(self._paused(start + timedelta(days=6)))
        self.assertFalse(self._paused(start + timedelta(days=8)))

        self._try(start + timedelta(days=8))
        self.assertTrue(self._paused(start + timedelta(days=37)))
        self.assertFalse(self._paused(start + timedelta(days=39)))

        self._try(start + timedelta(days=39))
        self.assertTrue(self._paused(start + timedelta(days=3650)))

    def test_no_tries_is_not_a_pause(self):
        generator = AIGenerator.find_or_create(session, self.MODEL, self.PROMPT)
        row = ExampleGenerationAttempt(
            meaning_id=self.meaning_id, cefr_level="A2", ai_generator=generator, tries=0, last_try_at=server_now()
        )
        self.assertFalse(row.is_paused((self.MODEL, self.PROMPT), server_now()))

    def test_a_new_prompt_or_model_starts_over(self):
        start = datetime(2026, 11, 10)
        for _ in range(3):
            self._try(start)
        self.assertFalse(self._paused(start, key=(self.MODEL, "v5")))
        self.assertFalse(self._paused(start, key=("better-model", self.PROMPT)))

        self._try(start, prompt="v5")
        row = ExampleGenerationAttempt.query.filter_by(meaning_id=self.meaning_id).one()
        self.assertEqual((row.generator_key(), row.tries), ((self.MODEL, "v5"), 1))

    def test_a_meaning_short_again_after_a_try_is_not_listed(self):
        # Also what happens when the validator rejects the examples after the
        # try: the meaning is short again, and it already had its try
        self.assertTrue(self._listed())
        self._try(server_now(), *intended_generator())
        self.assertFalse(self._listed())
        # --ignore-pause, e.g. after an anchoring fix
        self.assertTrue(self._listed(respect_pause=False))

    def test_a_covered_meaning_forgets_its_tries(self):
        self._try(server_now() - timedelta(days=100), *intended_generator())
        for i, level in enumerate(["A1", "A2", "A2"]):
            session.add(ExampleSentence(f"satz {i}", self.user.learned_language, self.user_word.meaning, cefr_level=level))
        session.commit()

        self._listed()  # listing, as the dry run does, writes nothing
        self.assertEqual(self._rows(), 1)

        forget_tries_of_covered_meanings()
        self.assertEqual(self._rows(), 0)

    def test_a_short_meaning_keeps_its_tries(self):
        self._try(server_now(), *intended_generator())
        forget_tries_of_covered_meanings()
        self.assertEqual(self._rows(), 1)

    def _generate(self, answered_by):
        from unittest.mock import patch
        from tools import prefetch_example_sentences_for_users as prefetch

        class Unanchorable:
            def generate_examples(self, **kwargs):
                return [{"sentence": "Ein Satz ohne das Wort.", "llm_model": answered_by, "prompt_version": "v4"}]

        with patch.object(prefetch, "get_llm_service", lambda **kwargs: Unanchorable()), patch(
            "zeeguu.core.llm_services.validation_service.UserWordValidationService.validate_and_fix",
            side_effect=lambda session, user_word, *a, **k: user_word,
        ):
            prefetch.generate_examples_for_user_word(self.user_word, "A2")

    def test_a_generation_by_the_intended_model_is_counted(self):
        self._generate(answered_by=intended_generator()[0])
        row = ExampleGenerationAttempt.query.filter_by(meaning_id=self.meaning_id, cefr_level="A2").one()
        self.assertEqual((row.generator_key(), row.tries), (intended_generator(), 1))

    def test_a_generation_by_the_fallback_is_not_counted(self):
        # A night on DeepSeek says nothing about what the primary model can do
        self._generate(answered_by="some-fallback-model")
        self.assertEqual(self._rows(), 0)

    def test_the_intended_model_follows_the_configured_provider(self):
        from unittest.mock import patch
        from zeeguu.core.llm_services import models

        with patch.dict("os.environ", {"LLM_PROVIDER": "deepseek"}):
            self.assertEqual(intended_generator()[0], models.DEEPSEEK_GENERAL)
        with patch.dict("os.environ", {"LLM_PROVIDER": "unified"}):
            self.assertEqual(intended_generator()[0], models.ANTHROPIC_GENERAL)
