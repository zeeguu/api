from unittest import TestCase

from zeeguu.core.translation_services.translator import _disambiguate_context


class DisambiguateContextTest(TestCase):
    def test_single_occurrence_unchanged(self):
        ctx = "Solen lyser en del af Venus op"
        self.assertEqual(_disambiguate_context("en", ctx, 2), ctx)

    def test_no_token_index_unchanged(self):
        ctx = "Med en kikkert kan du se en del af Venus"
        self.assertEqual(_disambiguate_context("en", ctx, None), ctx)

    def test_word_not_present_unchanged(self):
        ctx = "Solen lyser Venus op"
        self.assertEqual(_disambiguate_context("kikkert", ctx, 2), ctx)

    def test_tap_on_second_occurrence_drops_prefix(self):
        # The bug-report case (paraphrased): two "en"s, user tapped the 2nd.
        ctx = "Med en kikkert kan du se, at Solen kun lyser en del af Venus op"
        # "en" at whitespace-token positions 1 and 10.
        trimmed = _disambiguate_context("en", ctx, 10)
        # Only the second "en" should remain.
        self.assertEqual(trimmed.count(" en "), 1)
        self.assertIn("lyser en del", trimmed)
        self.assertNotIn("Med en kikkert", trimmed)

    def test_tap_on_first_occurrence_drops_suffix(self):
        ctx = "Med en kikkert kan du se, at Solen kun lyser en del af Venus op"
        # tap position close to the 1st "en" (whitespace-token pos 1).
        trimmed = _disambiguate_context("en", ctx, 1)
        self.assertIn("Med en kikkert", trimmed)
        self.assertNotIn("lyser en", trimmed)

    def test_tap_picks_nearest_of_three(self):
        ctx = "en blå bil og en rød bil og en grøn bil"
        # "en" at whitespace-token positions 0, 4, 8.
        trimmed = _disambiguate_context("en", ctx, 4)
        # The middle "en" must remain; the outer ones must be gone.
        self.assertIn("en rød bil", trimmed)
        self.assertNotIn("en blå", trimmed)
        self.assertNotIn("en grøn", trimmed)

    def test_off_by_one_from_punctuation_still_picks_right_match(self):
        # Stanza counts "," as its own token, so w_token_i may be one larger
        # than the whitespace-token position. The closest-match rule absorbs
        # the off-by-one.
        ctx = "Med en kikkert kan du se, at Solen kun lyser en del af Venus op"
        # Stanza-style token index for 2nd "en" = 11; whitespace pos = 10.
        trimmed = _disambiguate_context("en", ctx, 11)
        self.assertIn("lyser en del", trimmed)
        self.assertNotIn("Med en kikkert", trimmed)

    def test_word_with_regex_special_chars_no_crash(self):
        ctx = "foo (bar) baz (bar) qux"
        result = _disambiguate_context("(bar)", ctx, 1)
        # `re.escape` keeps the function from raising; correctness for tokens
        # that don't sit on `\b` boundaries isn't promised, but the call must
        # not crash.
        self.assertIsNotNone(result)

    def test_empty_context_returns_unchanged(self):
        self.assertEqual(_disambiguate_context("en", "", 0), "")

    def test_case_insensitive_match(self):
        ctx = "En del af Venus, og en del af Mars"
        trimmed = _disambiguate_context("en", ctx, 5)
        # Tap on the 2nd "en" — lowercase. The first "En" (capitalized,
        # sentence start) should be excluded.
        self.assertIn("en del af Mars", trimmed)
        self.assertNotIn("En del af Venus", trimmed)
