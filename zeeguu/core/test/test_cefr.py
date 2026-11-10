from zeeguu.core import cefr


def test_rank_orders_the_levels():
    assert [cefr.rank(level) for level in cefr.LEVELS] == [0, 1, 2, 3, 4, 5]


def test_a_split_level_counts_as_the_higher_one():
    assert cefr.rank("B1/B2") == cefr.rank("B2")
    assert cefr.single("B1/B2") == "B2"
    assert cefr.is_above("B1/B2", "B1")
    assert cefr.up_to("A2/B1") == ["A1", "A2", "B1"]


def test_not_a_level():
    for value in (None, "", "A0", "b1", "B3", "X/Y"):
        assert cefr.rank(value) is None
        assert cefr.single(value) is None
        assert cefr.up_to(value) == []
        assert cefr.below(value) == []
    assert not cefr.is_level("B1/B2")
    assert not cefr.is_above("C2", None)


def test_up_to_and_below():
    assert cefr.up_to("A1") == ["A1"]
    assert cefr.up_to("B1") == ["A1", "A2", "B1"]
    assert cefr.below("A1") == []
    assert cefr.below("B2") == ["A1", "A2", "B1"]


def test_harder():
    assert cefr.harder("B1", "B2") == "B2"
    assert cefr.harder("C1", "A2") == "C1"
    assert cefr.harder(None, "A2") == "A2"
    assert cefr.harder("A2", None) == "A2"
    assert cefr.harder("A2", "garbage") == "A2"


def test_parse():
    assert cefr.parse(" b1 ") == "B1"
    assert cefr.parse("B1/B2") is None
    assert cefr.parse(None) is None
    assert cefr.parse(3) is None


def test_stored_numbers():
    assert cefr.from_number(0) == "A0"
    assert cefr.from_number(6) == "C2"
    assert cefr.from_number(7) is None
    assert cefr.from_number(-1) is None
    assert cefr.from_number(None) is None
    assert [cefr.to_number(level) for level in cefr.STORED_LEVELS] == list(range(7))
    assert cefr.to_number("B1/B2") is None
