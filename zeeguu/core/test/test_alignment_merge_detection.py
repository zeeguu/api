import unittest

from zeeguu.core.translation_services.azure_alignment import (
    _target_shared_with_longer_source,
)


class TargetSharedWithLongerSourceTest(unittest.TestCase):
    """
    Smoke-tests for the N:1 alignment-merge detector that suppresses bad
    function-word translations like Danish "en" -> "binoculars".

    The mappings list mirrors Azure's parsed alignment shape:
        [((src_start, src_end), (tgt_start, tgt_end)), ...]
    """

    def test_function_word_merged_into_noun_is_detected(self):
        # "Med en kikkert" -> "With binoculars"
        #   Med (0:2)     -> With (0:3)
        #   en (4:5)      -> binoculars (5:14)   <- our tap
        #   kikkert (7:13)-> binoculars (5:14)   <- longer source, same target
        word_positions = [(4, 5)]  # "en"
        our_target_spans = [(5, 14)]
        mappings = [
            ((0, 2), (0, 3)),
            ((4, 5), (5, 14)),
            ((7, 13), (5, 14)),
        ]
        self.assertTrue(
            _target_shared_with_longer_source(word_positions, our_target_spans, mappings)
        )

    def test_content_word_tap_not_suppressed(self):
        # Same alignment, but the user tapped "kikkert" — they should get
        # "binoculars" back, not None.
        word_positions = [(7, 13)]  # "kikkert"
        our_target_spans = [(5, 14)]
        mappings = [
            ((0, 2), (0, 3)),
            ((4, 5), (5, 14)),
            ((7, 13), (5, 14)),
        ]
        self.assertFalse(
            _target_shared_with_longer_source(word_positions, our_target_spans, mappings)
        )

    def test_one_to_one_alignment_unaffected(self):
        # "altså" -> "thus", no shared target.
        word_positions = [(4, 8)]
        our_target_spans = [(4, 7)]
        mappings = [
            ((0, 2), (0, 2)),
            ((4, 8), (4, 7)),
            ((10, 14), (9, 12)),
        ]
        self.assertFalse(
            _target_shared_with_longer_source(word_positions, our_target_spans, mappings)
        )

    def test_one_to_many_target_unaffected(self):
        # Source word spans multiple target words; nothing else maps to those
        # target spans → no suppression.
        word_positions = [(0, 5)]
        our_target_spans = [(0, 3), (5, 9)]
        mappings = [
            ((0, 5), (0, 3)),
            ((0, 5), (5, 9)),
        ]
        self.assertFalse(
            _target_shared_with_longer_source(word_positions, our_target_spans, mappings)
        )

    def test_equal_length_shared_target_not_suppressed(self):
        # Two equal-length sources share a target. Without a length signal we
        # can't tell which is the "function word", so be conservative and
        # don't suppress.
        word_positions = [(0, 2)]
        our_target_spans = [(0, 4)]
        mappings = [
            ((0, 2), (0, 4)),
            ((4, 6), (0, 4)),
        ]
        self.assertFalse(
            _target_shared_with_longer_source(word_positions, our_target_spans, mappings)
        )

    def test_partially_overlapping_target_span_still_detected(self):
        # Other source's target span overlaps ours but isn't identical.
        word_positions = [(4, 5)]
        our_target_spans = [(5, 14)]
        mappings = [
            ((4, 5), (5, 14)),
            ((7, 13), (5, 9)),  # overlapping subset
        ]
        self.assertTrue(
            _target_shared_with_longer_source(word_positions, our_target_spans, mappings)
        )

    def test_no_word_positions_returns_false(self):
        self.assertFalse(_target_shared_with_longer_source([], [(0, 5)], []))

    def test_no_target_spans_returns_false(self):
        self.assertFalse(_target_shared_with_longer_source([(0, 2)], [], []))


if __name__ == "__main__":
    unittest.main()
