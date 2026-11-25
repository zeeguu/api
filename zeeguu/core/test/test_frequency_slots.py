"""Which words give up their practice slot (frequency_slots.py): no database."""

from zeeguu.core.word_scheduling.basicSR.frequency_slots import SlotWord, words_to_take_out


def word(uw_id, rank, text=None, level=0):
    """A SlotWord whose text is its own unless given."""
    return SlotWord(uw_id, rank, text or f"word{uw_id}", level)


def out_ids(scheduled, waiting):
    return [w.user_word_id for w in words_to_take_out(scheduled, waiting)]


def test_a_more_frequent_waiting_word_takes_the_slot():
    assert out_ids([word(1, 4_000, level=1)], [word(2, 3_999)]) == [1]


def test_a_rarer_or_equally_frequent_waiting_word_does_not():
    assert out_ids([word(1, 4_000, level=1)], [word(2, 4_000)]) == []
    assert out_ids([word(1, 4_000, level=1)], [word(2, 9_000)]) == []


def test_a_word_at_level_2_keeps_its_slot():
    assert out_ids([word(1, 9_000, level=2)], [word(2, 43)]) == []


def test_rarest_slots_go_first_while_the_waiting_word_is_more_frequent():
    scheduled = [
        word(1, 1_000, level=1),
        word(2, 9_000, level=1),
        word(3, 8_000, level=2),
        word(4, 5_000, level=0),
    ]
    waiting = [word(5, 3_000), word(6, 100), word(7, 1_200)]
    # 9,000 -> 100, 5,000 -> 1,200, then 1,000 vs 3,000: stop
    assert out_ids(scheduled, waiting) == [2, 4]


def test_a_word_without_rank_counts_as_rarest():
    assert out_ids([word(1, None, level=1)], [word(2, 50_000)]) == [1]
    assert out_ids([word(1, 50_000, level=1)], [word(2, None)]) == []


def test_nothing_waiting_nothing_taken_out():
    assert out_ids([word(1, 9_000, level=1)], []) == []


def test_a_rank_of_zero_is_a_rank():
    assert out_ids([word(1, 0, level=1)], [word(2, 50)]) == []
    assert out_ids([word(1, 50, level=1)], [word(2, 0)]) == [1]


def test_a_waiting_word_with_the_text_of_a_word_in_practice_stops_the_swaps():
    # another meaning of "bank": it would take the slot but never be shown
    scheduled = [word(1, 800, "bank", level=2), word(2, 9_000, "xyz", level=1)]
    waiting = [word(3, 800, "Bank")]
    assert out_ids(scheduled, waiting) == []


def test_two_waiting_words_with_one_text_take_one_slot():
    scheduled = [word(1, 9_000, "a", level=1), word(2, 8_000, "b", level=1)]
    waiting = [word(3, 100, "bank"), word(4, 200, "bank")]
    assert out_ids(scheduled, waiting) == [1]
