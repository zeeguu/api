"""A bookmark with two example links (an identical sentence stored at two
levels) used to raise in as_dictionary: find_by_bookmark's .one() found two
rows. That broke the exercise context swap and /alternative_sentences for the
word (user 4607, 'går ud fra', 10 Nov 2026)."""
from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.model.example_sentence_context import ExampleSentenceContext
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class ExampleLinkTwiceTest(ModelTestMixIn, TestCase):
    def test_a_bookmark_with_two_example_links_still_serializes(self):
        bookmark = BookmarkRule(UserRule().user).bookmark
        meaning = bookmark.user_word.meaning
        sentence = "Jeg går ud fra, at du kommer til festen i morgen."
        b1 = ExampleSentence(sentence, meaning.origin.language, meaning, cefr_level="B1")
        a1 = ExampleSentence(sentence, meaning.origin.language, meaning, cefr_level="A1")
        session.add_all([b1, a1])
        session.commit()
        session.add_all([ExampleSentenceContext(bookmark, b1), ExampleSentenceContext(bookmark, a1)])
        session.commit()

        # The newest link wins
        self.assertEqual(ExampleSentenceContext.find_by_bookmark(bookmark).example_sentence_id, a1.id)

    def test_no_link_is_none(self):
        bookmark = BookmarkRule(UserRule().user).bookmark
        self.assertIsNone(ExampleSentenceContext.find_by_bookmark(bookmark))
