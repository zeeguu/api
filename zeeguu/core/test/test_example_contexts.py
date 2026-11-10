"""Which words get their context swapped for a generated example.

The swap itself (locating the word in an example, tokenizing) is the same
code /alternative_sentences runs; these tests pin the gate: every context
that is not a good exercise sentence (whole, short, at or below the
learner's level), and only before the word's first exercise.
"""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.exercises import example_contexts
from zeeguu.core.model import Bookmark, Meaning, Phrase, UserLanguage, UserWord
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.exercises.example_contexts import (
    MAX_EXERCISE_SENTENCE_WORDS,
    _rank,
    is_fragment,
    next_unused_example_bookmark,
    replace_context_with_example,
    replace_contexts_not_good_for_exercise,
    why_not_a_good_exercise_context,
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

    def _exercise(self, user_word):
        exercise = ExerciseRule(ExerciseSessionRule(self.user).exerciseSession).exercise
        user_word.add_new_exercise(exercise)
        session.commit()

    def _second_bookmark_of(self, user_word):
        """Another sentence the learner looked the word up in, made its
        preferred one (what the arrows' /set_preferred_bookmark does)."""
        second = BookmarkRule(self.user).bookmark
        second.user_word = user_word
        session.add(second)
        session.commit()
        user_word.preferred_bookmark = second
        session.add(user_word)
        session.commit()
        return second

    def test_an_exercised_word_with_its_default_context_is_considered(self):
        fresh = self._user_word()
        exercised = self._user_word(left_ellipsis=True)
        self._exercise(exercised)

        with patch.object(example_contexts, "replace_context_with_example", return_value=True) as swap:
            swapped = replace_contexts_not_good_for_exercise(session, [fresh, exercised])

        self.assertEqual(swapped, 2)
        self.assertEqual([c.args[1] for c in swap.call_args_list], [fresh, exercised])

    def test_a_context_the_learner_picked_is_left_alone(self):
        # The learner looked the word up twice and picked the second sentence
        # with the arrows (/set_preferred_bookmark)
        picked = self._user_word()
        first = picked.preferred_bookmark
        second = self._second_bookmark_of(picked)
        self.assertGreater(second.id, first.id)
        self._exercise(picked)

        with patch.object(example_contexts, "replace_context_with_example", return_value=True) as swap:
            self.assertEqual(replace_contexts_not_good_for_exercise(session, [picked]), 0)
        swap.assert_not_called()

    def test_a_picked_context_counts_only_once_exercised(self):
        # Never exercised: no exercise to have picked it in, so it is fair game
        picked = self._user_word()
        second = self._second_bookmark_of(picked)

        with patch.object(example_contexts, "replace_context_with_example", return_value=True) as swap:
            self.assertEqual(replace_contexts_not_good_for_exercise(session, [picked]), 1)

    def test_a_failing_swap_does_not_fail_the_rest(self):
        first = self._user_word(left_ellipsis=True)
        second = self._user_word(left_ellipsis=True)

        def swap(_session, user_word):
            if user_word is first:
                raise RuntimeError("tokenizer down")
            return True

        with patch.object(example_contexts, "replace_context_with_example", side_effect=swap):
            self.assertEqual(replace_contexts_not_good_for_exercise(session, [first, second]), 1)

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

        with patch.object(example_contexts, "replace_context_with_example", side_effect=swap):
            self.assertEqual(replace_contexts_not_good_for_exercise(session, [first, second]), 1)


class GoodExerciseContextTest(ModelTestMixIn, TestCase):
    """Only 24% of the contexts waiting to be practiced were good exercise
    sentences (10 Nov 2026); an A2 learner got B2 article sentences and looked
    up half of each (user 6885, 9 Nov 2026)."""

    SHORT = "Der Hund schläft im Garten."

    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self._set_level(2)  # A2

    def _set_level(self, level):
        user_language = UserLanguage.find_or_create(session, self.user, self.user.learned_language)
        user_language.cefr_level = level
        session.commit()

    def _user_word(self, article_level="A2", sentence=SHORT, context_type=ContextType.ARTICLE_FRAGMENT):
        bookmark = BookmarkRule(self.user).bookmark
        bookmark.text.article.cefr_level = article_level
        bookmark.context.context_type = ContextType.find_by_type(context_type)
        bookmark.context.text.content = sentence
        user_word = bookmark.user_word
        user_word.preferred_bookmark = bookmark
        session.add_all([bookmark, user_word])
        session.commit()
        return user_word

    def _why(self, user_word, level="A2"):
        return why_not_a_good_exercise_context(user_word.preferred_bookmark, level)

    def test_a_short_whole_sentence_at_or_below_the_level_is_good(self):
        self.assertIsNone(self._why(self._user_word("A2")))
        self.assertIsNone(self._why(self._user_word("A1")))

    def test_even_one_level_above_is_too_much(self):
        self.assertEqual(self._why(self._user_word("B1")), "above level")

    def test_a_split_assessment_counts_as_the_higher_level(self):
        # Split levels only come from effective_cefr_level; the column can't hold them
        self.assertEqual(_rank("B1/B2"), _rank("B2"))
        self.assertEqual(_rank("A2/B1"), _rank("B1"))

    def test_a_long_sentence_is_not_good(self):
        just_right = " ".join(["Wort"] * MAX_EXERCISE_SENTENCE_WORDS)
        self.assertIsNone(self._why(self._user_word(sentence=just_right)))
        self.assertEqual(self._why(self._user_word(sentence=just_right + " mehr")), "too long")

    def test_a_fragment_is_not_good(self):
        user_word = self._user_word()
        user_word.preferred_bookmark.context.right_ellipsis = True
        session.commit()
        self.assertEqual(self._why(user_word), "fragment")

    def test_an_unknown_level_is_not_good(self):
        self.assertEqual(self._why(self._user_word(None)), "level unknown")
        self.assertEqual(self._why(self._user_word(context_type=ContextType.WEB_FRAGMENT)), "level unknown")

    def test_level_adapted_and_example_contexts_are_good(self):
        adapted = self._user_word("C1", context_type=ContextType.LEVEL_ADAPTED_ARTICLE_SUMMARY)
        self.assertIsNone(self._why(adapted))
        example = self._user_word("C1", sentence="x " * 30, context_type=ContextType.EXAMPLE_SENTENCE)
        self.assertIsNone(self._why(example))

    def test_a_context_that_is_not_good_asks_for_an_example_at_the_learners_level(self):
        user_word = self._user_word("B2")
        with patch.object(example_contexts, "next_unused_example_bookmark", return_value=None) as find:
            self.assertFalse(replace_context_with_example(session, user_word))
        self.assertEqual(find.call_args.kwargs, {"max_level": "A2"})

    def test_a_fragment_too_only_gets_an_example_at_the_learners_level(self):
        user_word = self._user_word()
        user_word.preferred_bookmark.context.left_ellipsis = True
        session.commit()
        with patch.object(example_contexts, "next_unused_example_bookmark", return_value=None) as find:
            self.assertFalse(replace_context_with_example(session, user_word))
        self.assertEqual([call.kwargs for call in find.call_args_list], [{"max_level": "A2"}])

    def test_a_good_context_stays(self):
        user_word = self._user_word("A2")
        with patch.object(example_contexts, "next_unused_example_bookmark") as find:
            self.assertFalse(replace_context_with_example(session, user_word))
        find.assert_not_called()

    def test_without_a_learner_level_examples_are_picked_at_a2(self):
        self._set_level(None)
        user_word = self._user_word("B1")
        with patch.object(example_contexts, "next_unused_example_bookmark", return_value=None) as find:
            self.assertFalse(replace_context_with_example(session, user_word))
        self.assertEqual(find.call_args.kwargs, {"max_level": "A2"})

    def test_examples_above_the_learners_level_are_skipped(self):
        user_word = self._user_word("B2")
        for sentence, level in [("hard", "B1"), ("easy", "A1"), ("unknown", None)]:
            session.add(
                ExampleSentence(sentence, self.user.learned_language, user_word.meaning, cefr_level=level)
            )
        session.commit()

        offered = []

        def bookmark_for(_session, _user, _user_word, example):
            offered.append(example.sentence)
            return None

        with patch.object(example_contexts, "bookmark_for_example", side_effect=bookmark_for):
            next_unused_example_bookmark(session, user_word, max_level="A2")
        self.assertEqual(offered, ["easy"])


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


class AnchorableExamplesTest(ModelTestMixIn, TestCase):
    def test_examples_without_the_word_are_dropped(self):
        from zeeguu.core.model import Language

        danish = Language.find_or_create("da")
        examples = [
            {"sentence": "Selv børnene kunne løse opgaven."},
            {"sentence": "_____ min bedstemor bruger internettet."},
        ]
        self.assertEqual(
            example_contexts.anchorable_examples(examples, "selv", danish),
            [{"sentence": "Selv børnene kunne løse opgaven."}],
        )

    def test_examples_are_kept_when_tokenizing_fails(self):
        from zeeguu.core.model import Language

        danish = Language.find_or_create("da")
        examples = [{"sentence": "Selv børnene kunne løse opgaven."}]
        with patch.object(example_contexts, "find_word_positions_in_text", side_effect=KeyError("bug")):
            self.assertEqual(example_contexts.anchorable_examples(examples, "selv", danish), examples)
