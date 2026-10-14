"""Which meaning a lookup returns when case variants exist.

Prod has ~2.6k groups of meanings that differ only in case (or, through the
accent-insensitive collation, only in accents). Picking the first one gave
user 8 a second word: 'Mientras' next to their 'mientras' (user_word 532196).
The accent half only shows on MySQL; SQLite compares accents strictly.
"""
from unittest import TestCase

import zeeguu.core
from zeeguu.core.model import Meaning, Phrase, UserWord
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class MeaningCaseVariantsTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.learned = self.user.learned_language
        self.native = self.user.native_language
        # Built directly: find_or_create would merge them, but prod has such
        # pairs from older data (meanings 131704 'Mientras' / 264078 'mientras').
        self.capitalised = self._meaning("Mientras", "While")
        self.lower = self._meaning("mientras", "while")

    def _meaning(self, origin, translation):
        meaning = Meaning(Phrase(origin, self.learned), Phrase(translation, self.native))
        session.add(meaning)
        session.commit()
        return meaning

    def _find(self, origin, translation, user=None):
        return Meaning.find_or_create(
            session, origin, self.learned.code, translation, self.native.code, user=user
        )

    def test_exact_spelling_wins_over_the_older_variant(self):
        self.assertEqual(self._find("mientras", "while").id, self.lower.id)
        self.assertEqual(self._find("Mientras", "While").id, self.capitalised.id)

    def test_a_meaning_the_user_already_has_wins(self):
        UserWord.find_or_create(session, self.user, self.lower)
        session.commit()
        # Typed at the start of a sentence, but the learner already has the word.
        self.assertEqual(self._find("Mientras", "While", user=self.user).id, self.lower.id)

    def test_without_a_variant_case_is_still_merged(self):
        only = self._meaning("aunque", "although")
        self.assertEqual(self._find("Aunque", "Although").id, only.id)


class CanonicalFormTest(TestCase):
    def test_keeps_accents_merges_case_and_unicode_forms(self):
        canon = Meaning._canonicalize
        self.assertEqual(canon(" Mientras "), canon("mientras"))
        # decomposed é (e + combining acute) is the same word as é
        self.assertEqual(canon("accompagné"), canon("accompagné"))
        self.assertNotEqual(canon("accompagne"), canon("accompagné"))
