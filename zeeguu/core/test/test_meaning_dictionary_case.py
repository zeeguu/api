"""The validator's dictionary case replaces the case a meaning was first
translated in: "Dette" -> "This" (start of a sentence) became the only
meaning for Danish "dette" (meaning 135455)."""
from unittest import TestCase

import zeeguu.core
from zeeguu.core.model import Meaning, Phrase
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class MeaningDictionaryCaseTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        user = UserRule().user
        self.learned = user.learned_language
        self.native = user.native_language

    def _meaning(self, origin, translation):
        meaning = Meaning(Phrase(origin, self.learned), Phrase(translation, self.native))
        session.add(meaning)
        session.commit()
        return meaning

    def _spelled(self, meaning):
        return meaning.origin.content, meaning.translation.content

    def test_sentence_initial_case_is_dropped(self):
        meaning = self._meaning("Dette", "This")
        self.assertTrue(meaning.take_case_from(session, "dette", "this"))
        self.assertEqual(self._spelled(meaning), ("dette", "this"))

    def test_the_old_phrase_stays_for_other_meanings(self):
        capitalised = self._meaning("Dette", "This")
        other = Meaning(capitalised.origin, Phrase("That", self.native))
        session.add(other)
        session.commit()
        capitalised.take_case_from(session, "dette", "this")
        session.commit()
        self.assertEqual(self._spelled(other), ("Dette", "That"))

    def test_an_existing_spelling_is_reused(self):
        lower = Phrase("dette", self.learned)
        session.add(lower)
        meaning = self._meaning("Dette", "This")
        meaning.take_case_from(session, "dette", "this")
        self.assertEqual(meaning.origin.id, lower.id)

    def test_only_case_is_taken(self):
        meaning = self._meaning("Dette", "This")
        self.assertFalse(meaning.take_case_from(session, "denne", "that"))
        self.assertEqual(self._spelled(meaning), ("Dette", "This"))

    def test_only_the_first_letter_may_change(self):
        meaning = self._meaning("Dette", "This")
        self.assertFalse(meaning.take_case_from(session, "DETTE", "tHIS"))
        self.assertEqual(self._spelled(meaning), ("Dette", "This"))

    def test_a_capital_the_language_keeps_is_kept(self):
        meaning = self._meaning("Mandag", "Monday")
        meaning.take_case_from(session, "mandag", "Monday")
        self.assertEqual(self._spelled(meaning), ("mandag", "Monday"))

    def test_no_dictionary_case_changes_nothing(self):
        meaning = self._meaning("Dette", "This")
        self.assertFalse(meaning.take_case_from(session, None, None))
