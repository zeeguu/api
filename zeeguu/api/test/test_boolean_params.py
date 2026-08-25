from zeeguu.api.utils.parse_json_boolean import (
    get_boolean_from_params,
    parse_json_boolean,
)


def test_parses_the_two_json_spellings():
    assert parse_json_boolean("true") is True
    assert parse_json_boolean("false") is False


def test_is_case_insensitive():
    # Some clients send "True"; before, that read as neither true nor false.
    assert parse_json_boolean("True") is True
    assert parse_json_boolean("FALSE") is False


def test_anything_else_is_none():
    assert parse_json_boolean(None) is None
    assert parse_json_boolean("") is None
    assert parse_json_boolean("yes") is None
    assert parse_json_boolean("1") is None


def test_reads_the_named_param():
    params = {"detailed": "true", "quiet": "false"}

    assert get_boolean_from_params(params, "detailed") is True
    assert get_boolean_from_params(params, "quiet") is False


def test_default_stands_in_for_a_param_that_was_not_sent():
    assert get_boolean_from_params({}, "detailed", default=False) is False
    assert get_boolean_from_params({}, "detailed", default=True) is True


def test_default_is_none_so_absent_stays_distinguishable_from_false():
    # What a partial update needs: "not told" must not read as "set it false".
    assert get_boolean_from_params({}, "detailed") is None
    assert get_boolean_from_params({"detailed": "false"}, "detailed") is False


def test_an_unparseable_value_falls_back_to_the_default():
    assert get_boolean_from_params({"detailed": "maybe"}, "detailed", default=False) is False
