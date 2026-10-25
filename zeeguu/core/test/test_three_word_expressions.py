"""Three-word expressions are studied: on 25 Oct 2026 correcting past
validator fixes moved learners to "de son côté" and "Ligue des champions", and
the old two-word limit took them out of study."""
from types import SimpleNamespace
from unittest import TestCase

from zeeguu.core.bookmark_quality.negative_qualities import origin_has_too_many_words
from zeeguu.core.model.meaning import PhraseType


def word(origin, phrase_type=None):
    return SimpleNamespace(
        meaning=SimpleNamespace(origin=SimpleNamespace(content=origin), phrase_type=phrase_type)
    )


class ThreeWordExpressionsTest(TestCase):
    def test_three_words_are_not_too_many(self):
        self.assertFalse(origin_has_too_many_words(word("de son côté")))

    def test_a_longer_set_phrase_is_not_too_many(self):
        self.assertFalse(origin_has_too_many_words(word("tomber dans les pommes", PhraseType.IDIOM)))

    def test_a_longer_stretch_of_text_is(self):
        self.assertTrue(origin_has_too_many_words(word("le gouvernement a annoncé hier")))
        self.assertTrue(
            origin_has_too_many_words(word("le gouvernement a annoncé", PhraseType.ARBITRARY_MULTI_WORD))
        )
