"""Which words get their fragment context swapped for a generated example.

The swap itself (locating the word in an example, tokenizing) is the same
code /alternative_sentences runs; these tests pin the gate: only fragments,
and only before the word's first exercise.
"""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.exercises import example_contexts
from zeeguu.core.model import Bookmark, Meaning, Phrase, UserWord
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.exercises.example_contexts import (
    is_fragment,
    replace_fragments_before_first_exercise,
)
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class ExampleContextsTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user

    def _user_word(self, left_ellipsis=False, right_ellipsis=False):
        bookmark = BookmarkRule(self.user).bookmark
        bookmark.context.left_ellipsis = left_ellipsis
        bookmark.context.right_ellipsis = right_ellipsis
        user_word = bookmark.user_word
        user_word.preferred_bookmark = bookmark
        session.add_all([bookmark, user_word])
        session.commit()
        return user_word

    def test_is_fragment(self):
        self.assertTrue(is_fragment(self._user_word(left_ellipsis=True).preferred_bookmark))
        self.assertTrue(is_fragment(self._user_word(right_ellipsis=True).preferred_bookmark))
        self.assertFalse(is_fragment(self._user_word().preferred_bookmark))

    def test_only_unexercised_fragments_are_swapped(self):
        whole = self._user_word()
        fragment = self._user_word(left_ellipsis=True)
        exercised_fragment = self._user_word(right_ellipsis=True)
        exercise = ExerciseRule(ExerciseSessionRule(self.user).exerciseSession).exercise
        exercised_fragment.add_new_exercise(exercise)
        session.commit()

        with patch.object(example_contexts, "replace_fragment_with_example", return_value=True) as swap:
            swapped = replace_fragments_before_first_exercise(
                session, [whole, fragment, exercised_fragment]
            )

        self.assertEqual(swapped, 1)
        self.assertEqual([c.args[1] for c in swap.call_args_list], [fragment])

    def test_a_failing_swap_does_not_fail_the_rest(self):
        first = self._user_word(left_ellipsis=True)
        second = self._user_word(left_ellipsis=True)

        def swap(_session, user_word):
            if user_word is first:
                raise RuntimeError("tokenizer down")
            return True

        with patch.object(example_contexts, "replace_fragment_with_example", side_effect=swap):
            self.assertEqual(replace_fragments_before_first_exercise(session, [first, second]), 1)

    def test_a_failed_flush_is_rolled_back_before_the_next_word(self):
        # What happened on prod: the preferred_bookmark integrity check fails
        # the flush, after which any read of the session raises until rollback.
        first = self._user_word(left_ellipsis=True)
        second = self._user_word(left_ellipsis=True)

        def swap(_session, user_word):
            if user_word is first:
                user_word.preferred_bookmark = second.preferred_bookmark
                _session.flush()
            return True

        with patch.object(example_contexts, "replace_fragment_with_example", side_effect=swap):
            self.assertEqual(replace_fragments_before_first_exercise(session, [first, second]), 1)


class ExampleBookmarkStaysOnTheWordTest(ModelTestMixIn, TestCase):
    """Meaning lookup ignores case. A learner's 'mientras' must not resolve to
    an older 'Mientras' meaning and get a second word (user_word 532196)."""

    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        learned = self.user.learned_language.code
        native = self.user.native_language.code
        # The older capitalised meaning is what the strings resolve to.
        self.older = Meaning.find_or_create(session, "Mientras", learned, "While", native)
        # Built directly: find_or_create can't make a case variant any more,
        # but prod has such pairs from older data (meanings 131704 / 264078).
        self.meaning = Meaning(
            Phrase("mientras", self.user.learned_language),
            Phrase("while", self.user.native_language),
        )
        session.add(self.meaning)
        session.commit()
        self.user_word = UserWord.find_or_create(session, self.user, self.meaning)
        session.commit()

    def test_bookmark_goes_to_the_given_word(self):
        example = ExampleSentence(
            "Mientras comíamos, empezó a llover.", self.user.learned_language, self.meaning
        )
        session.add(example)
        session.commit()
        words_before = UserWord.query.filter_by(user_id=self.user.id).count()

        bookmark = Bookmark.find_or_create(
            session,
            self.user,
            "mientras",
            self.user.learned_language.code,
            "while",
            self.user.native_language.code,
            "Mientras comíamos, empezó a llover.",
            None,
            None,
            sentence_i=0,
            token_i=0,
            total_tokens=1,
            c_sentence_i=0,
            c_token_i=0,
            context_identifier=ContextIdentifier(
                context_type=ContextType.EXAMPLE_SENTENCE, example_sentence_id=example.id
            ),
            translation_source="generated_example",
            user_word=self.user_word,
        )

        self.assertEqual(bookmark.user_word_id, self.user_word.id)
        self.assertEqual(UserWord.query.filter_by(user_id=self.user.id).count(), words_before)

    def test_a_word_of_another_user_is_refused(self):
        other_user = UserRule().user
        with self.assertRaises(ValueError):
            Bookmark.find_or_create(
                session,
                other_user,
                "mientras",
                self.user.learned_language.code,
                "while",
                self.user.native_language.code,
                "Mientras comíamos, empezó a llover.",
                None,
                None,
                translation_source="generated_example",
                user_word=self.user_word,
            )
