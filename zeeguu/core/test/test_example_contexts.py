"""Which words get their fragment context swapped for a generated example.

The swap itself (locating the word in an example, tokenizing) is the same
code /alternative_sentences runs; these tests pin the gate: only fragments,
and only before the word's first exercise.
"""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.exercises import example_contexts
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
