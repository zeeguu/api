"""A sentence that is what is wrong never costs the learner their meaning.

A generated example was generated for the meaning, so when the validator would
not pass the meaning in it, the example is what is wrong: "selv" = "even" must
not become "selv om" because one example used "selv om". Since June 2026, 395
learners' words were moved to another meaning this way. A sentence the
validator calls broken says nothing about the word either. Both get another
sentence before the word is given up on.
"""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.exercises.example_contexts import usable_examples
from zeeguu.core.llm_services import translation_validator
from zeeguu.core.llm_services.translation_validator import ValidationResult
from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.model import Bookmark, Meaning
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.model.example_sentence_misfit import ExampleSentenceMisfit
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session

BROKEN = ValidationResult(is_valid=False, gave_up="BROKEN_SENTENCE", reason="the sentence is cut off")
VALID = ValidationResult(is_valid=True, frequency="common", phrase_type="single_word", cefr_level="A1")
EXPANDED = ValidationResult(is_valid=False, corrected_word="selv om", corrected_translation="even though",
                            reason="'selv om' is the unit here")


def validator_judging(verdict_for):
    """A validator whose verdict depends only on the sentence."""
    return lambda: SimpleNamespace(
        validate_translation=lambda word, translation, context, source_lang, target_lang: verdict_for(context)
    )


class GeneratedSentenceKeepsCardTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.own = BookmarkRule(self.user).bookmark
        self.own.translation_source = "reading"
        self.user_word = self.own.user_word
        self.meaning = self.user_word.meaning
        self.meaning.validated = Meaning.NOT_VALIDATED
        word = self.meaning.origin.content

        self.example = ExampleSentence(f"Hun kom {word} om det regnede.", self.user.learned_language, self.meaning)
        session.add(self.example)
        session.commit()
        self.example_bookmark = Bookmark.find_or_create(
            session,
            self.user,
            word,
            self.user.learned_language.code,
            self.meaning.translation.content,
            self.user.native_language.code,
            self.example.sentence,
            None,
            None,
            sentence_i=0,
            token_i=2,
            total_tokens=1,
            c_sentence_i=0,
            c_token_i=0,
            context_identifier=ContextIdentifier(
                context_type=ContextType.EXAMPLE_SENTENCE, example_sentence_id=self.example.id
            ),
            translation_source="generated_example",
            user_word=self.user_word,
        )
        self.user_word.preferred_bookmark = self.example_bookmark
        session.add_all([self.own, self.user_word, self.meaning])
        session.commit()

    def _validate(self, verdict_for):
        with patch.object(translation_validator, "TranslationValidator", validator_judging(verdict_for)):
            return UserWordValidationService.validate_and_fix(session, self.user_word)

    def test_a_fix_in_a_generated_example_keeps_the_card_and_drops_the_example(self):
        example = self.example.sentence

        result = self._validate(lambda context: EXPANDED if context == example else VALID)

        self.assertIs(result, self.user_word)
        self.assertEqual(self.user_word.meaning_id, self.meaning.id)  # the card is what it was
        self.assertEqual(self.user_word.preferred_bookmark_id, self.own.id)  # judged in the learner's sentence
        self.assertEqual(self.meaning.validated, Meaning.VALID)
        self.assertIsNotNone(session.get(ExampleSentenceMisfit, self.example.id))
        self.assertNotIn(self.example, usable_examples(self.meaning.id))

    def test_after_a_bad_example_a_reader_fragment_of_the_learners_own_is_skipped(self):
        # a fragment is context for the meaning, not for study
        self.own.context.left_ellipsis = True
        session.add(self.own.context)
        session.commit()
        example = self.example.sentence

        with patch("zeeguu.core.exercises.example_contexts.next_unused_example_bookmark", return_value=None):
            result = self._validate(lambda context: EXPANDED if context == example else VALID)

        self.assertIsNone(result)  # no whole sentence and no other example: given up
        self.assertNotEqual(self.user_word.preferred_bookmark_id, self.own.id)
        self.assertEqual(self.user_word.meaning_id, self.meaning.id)

    def test_no_sentence_left_gives_up_without_touching_the_card(self):
        # Only generated sentences, and the card fits none of them
        self.own.translation_source = "generated_example"
        session.add(self.own)
        session.commit()

        result = self._validate(lambda context: EXPANDED)

        self.assertIsNone(result)
        self.assertEqual(self.user_word.meaning_id, self.meaning.id)
        self.assertFalse(self.user_word.fit_for_study)
        self.assertNotEqual(self.meaning.validated, Meaning.INVALID)

    def test_a_valid_verdict_in_a_generated_example_is_kept(self):
        result = self._validate(lambda context: VALID)

        self.assertIs(result, self.user_word)
        self.assertEqual(self.user_word.preferred_bookmark_id, self.example_bookmark.id)
        self.assertIsNone(session.get(ExampleSentenceMisfit, self.example.id))


class BrokenOwnSentenceTest(ModelTestMixIn, TestCase):
    """The learner's own sentence is broken ("Det ganske særl"), and the word
    has a second sentence of the learner's own."""

    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.broken = BookmarkRule(self.user).bookmark
        self.broken.translation_source = "reading"
        self.user_word = self.broken.user_word
        self.meaning = self.user_word.meaning
        self.meaning.validated = Meaning.NOT_VALIDATED
        self.other = Bookmark.find_or_create(
            session,
            self.user,
            self.meaning.origin.content,
            self.user.learned_language.code,
            self.meaning.translation.content,
            self.user.native_language.code,
            f"Det er {self.meaning.origin.content} her.",
            None,
            None,
            sentence_i=0,
            token_i=2,
            total_tokens=1,
            c_sentence_i=0,
            c_token_i=0,
            context_identifier=ContextIdentifier(context_type=ContextType.USER_EDITED_TEXT),
            translation_source="reading",
            user_word=self.user_word,
        )
        self.user_word.preferred_bookmark = self.broken
        session.add_all([self.broken, self.user_word, self.meaning])
        session.commit()

    def _validate(self, verdict_for, example_bookmark=None):
        with patch.object(translation_validator, "TranslationValidator", validator_judging(verdict_for)), \
                patch("zeeguu.core.exercises.example_contexts.next_unused_example_bookmark",
                      return_value=example_bookmark) as next_example:
            result = UserWordValidationService.validate_and_fix(session, self.user_word)
        return result, next_example

    def _example_bookmark(self):
        example = ExampleSentence(f"Vi så {self.meaning.origin.content} i går.", self.user.learned_language, self.meaning)
        session.add(example)
        session.commit()
        return Bookmark.find_or_create(
            session, self.user, self.meaning.origin.content, self.user.learned_language.code,
            self.meaning.translation.content, self.user.native_language.code, example.sentence, None, None,
            sentence_i=0, token_i=2, total_tokens=1, c_sentence_i=0, c_token_i=0,
            context_identifier=ContextIdentifier(context_type=ContextType.EXAMPLE_SENTENCE, example_sentence_id=example.id),
            translation_source="generated_example", user_word=self.user_word,
        )

    def test_a_broken_own_sentence_goes_to_examples_not_to_another_own_sentence(self):
        broken = self.broken.get_context()
        example_bookmark = self._example_bookmark()

        result, _ = self._validate(lambda context: BROKEN if context == broken else VALID, example_bookmark)

        self.assertIs(result, self.user_word)
        self.assertTrue(self.user_word.fit_for_study)
        self.assertEqual(self.user_word.preferred_bookmark_id, example_bookmark.id)  # not self.other
        self.assertEqual(self.meaning.validated, Meaning.VALID)

    def test_a_broken_own_sentence_with_no_example_gives_up_without_touching_the_meaning(self):
        result, _ = self._validate(lambda context: BROKEN)

        self.assertIsNone(result)
        self.assertFalse(self.user_word.fit_for_study)
        self.assertEqual(self.meaning.validated, Meaning.NOT_VALIDATED)
