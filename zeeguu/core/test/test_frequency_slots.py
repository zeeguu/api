"""Which words give up their practice slot (frequency_slots.py): no database."""

from zeeguu.core.word_scheduling.basicSR.frequency_slots import SlotWord, words_to_take_out


def out_ids(scheduled, waiting):
    return [w.user_word_id for w in words_to_take_out(scheduled, waiting)]


def test_a_more_frequent_waiting_word_takes_the_slot():
    assert out_ids([SlotWord(1, 4_000, level=1)], [SlotWord(2, 3_999)]) == [1]


def test_a_rarer_or_equally_frequent_waiting_word_does_not():
    assert out_ids([SlotWord(1, 4_000, level=1)], [SlotWord(2, 4_000)]) == []
    assert out_ids([SlotWord(1, 4_000, level=1)], [SlotWord(2, 9_000)]) == []


def test_a_word_at_level_2_keeps_its_slot():
    assert out_ids([SlotWord(1, 9_000, level=2)], [SlotWord(2, 43)]) == []


def test_rarest_slots_go_first_while_the_waiting_word_is_more_frequent():
    scheduled = [
        SlotWord(1, 1_000, level=1),
        SlotWord(2, 9_000, level=1),
        SlotWord(3, 8_000, level=2),
        SlotWord(4, 5_000, level=0),
    ]
    waiting = [SlotWord(5, 3_000), SlotWord(6, 100), SlotWord(7, 1_200)]
    # 9,000 -> 100, 5,000 -> 1,200, then 1,000 vs 3,000: stop
    assert out_ids(scheduled, waiting) == [2, 4]


def test_a_word_without_rank_counts_as_rarest():
    assert out_ids([SlotWord(1, None, level=1)], [SlotWord(2, 50_000)]) == [1]
    assert out_ids([SlotWord(1, 50_000, level=1)], [SlotWord(2, None)]) == []


def test_nothing_waiting_nothing_taken_out():
    assert out_ids([SlotWord(1, 9_000, level=1)], []) == []
