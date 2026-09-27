"""
What the Explain cache is keyed on.

The key is what makes the cache safe to share between learners: everything the
explanation depends on has to be in it, or one learner gets prose written for
another's question. These tests pin the four things that must separate entries
and the one that must not.

No LLM here on purpose -- the generation path is exercised by hand against the
real service; what can go quietly wrong in production is the key.
"""

from unittest import TestCase

from zeeguu.core.model.selection_explanation import SelectionExplanation


class SelectionExplanationKeyTest(TestCase):

    SENTENCE = "Han troede, han kunne narre alle, men han er bare en narrøv."

    def test_same_sentence_hashes_the_same(self):
        self.assertEqual(
            SelectionExplanation.hash_of(self.SENTENCE),
            SelectionExplanation.hash_of(self.SENTENCE),
        )

    def test_different_sentence_hashes_differently(self):
        # The whole point of passing context: the same word in another sentence
        # is a different question and must not reuse the answer.
        other = "Han er en narrøv, men han mener det ikke ondt."
        self.assertNotEqual(
            SelectionExplanation.hash_of(self.SENTENCE),
            SelectionExplanation.hash_of(other),
        )

    def test_hash_is_hex_of_fixed_width(self):
        # The column is VARCHAR(64); a longer digest would be silently truncated
        # and start colliding.
        h = SelectionExplanation.hash_of(self.SENTENCE)
        self.assertEqual(len(h), 64)
        int(h, 16)  # raises if it is not hex

    def test_non_ascii_sentence_hashes(self):
        # Danish, Bulgarian and Greek all arrive here; a hash that assumed ascii
        # would throw on the first æ.
        for sentence in [
            "Han gik helt agurk, da han hørte nyheden.",
            "Той отиде в библиотеката, за да чете.",
            "Πήγε στη βιβλιοθήκη για να διαβάσει.",
        ]:
            self.assertEqual(len(SelectionExplanation.hash_of(sentence)), 64)

    def test_whitespace_is_significant(self):
        # Contexts are stripped before they reach the cache; if that ever stops
        # happening, two spellings of one sentence would each pay for a call.
        self.assertNotEqual(
            SelectionExplanation.hash_of(self.SENTENCE),
            SelectionExplanation.hash_of(self.SENTENCE + " "),
        )
