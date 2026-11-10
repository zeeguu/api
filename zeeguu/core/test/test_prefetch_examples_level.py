"""The nightly example prefetch covers the words the exercises will show next,
at the learner's level. An A2 learner's new words used to have no examples,
or B1-C2 ones (user 6885, 9 Nov 2026)."""

from datetime import datetime
from unittest import TestCase

import zeeguu.core
from tools.prefetch_example_sentences_for_users import get_user_words_needing_examples
from zeeguu.core.model import UserLanguage
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

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
