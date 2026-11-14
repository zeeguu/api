"""
A quote mark inside an expression must not turn it into a separated MWE.

No Flask app or DB needed: _apply_mwe_groups works on plain token dicts.
"""

from zeeguu.core.mwe.enricher import MWEDetector


def _tok(text, punct=False):
    return {"text": text, "is_punct": punct, "is_symbol": False}


def _detector():
    # Skip __init__: it loads the Stanza strategy, which these tests don't use.
    return MWEDetector.__new__(MWEDetector)


def test_an_expression_split_only_by_a_quote_mark_is_not_grouped():
    # ... Rasmus Wallbridge blev "offentligt ydmyget i månedsvis"
    tokens = [_tok("Wallbridge"), _tok("blev"), _tok('"', punct=True),
              _tok("offentligt"), _tok("ydmyget"), _tok("i"), _tok("månedsvis")]
    group = {"head_idx": 4, "dependent_indices": [1, 3], "type": "grammatical"}

    _detector()._apply_mwe_groups(tokens, [group], 0, 0)

    assert not any("mwe_group_id" in t for t in tokens)


def test_an_expression_separated_by_a_word_is_still_grouped():
    # rufe dich an
    tokens = [_tok("Ich"), _tok("rufe"), _tok("dich"), _tok("an"), _tok(".", punct=True)]
    group = {"head_idx": 1, "dependent_indices": [3], "type": "particle_verb"}

    _detector()._apply_mwe_groups(tokens, [group], 0, 0)

    assert tokens[1]["mwe_is_separated"] is True
    assert tokens[3]["mwe_group_id"] == tokens[1]["mwe_group_id"]
    assert "mwe_group_id" not in tokens[2]


def test_an_adjacent_expression_is_still_grouped():
    tokens = [_tok("Han"), _tok("blev"), _tok("ydmyget")]
    group = {"head_idx": 2, "dependent_indices": [1], "type": "grammatical"}

    _detector()._apply_mwe_groups(tokens, [group], 0, 0)

    assert tokens[1]["mwe_is_separated"] is False
    assert tokens[2]["mwe_group_id"] == tokens[1]["mwe_group_id"]
