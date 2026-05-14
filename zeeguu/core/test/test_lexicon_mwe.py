"""
Unit tests for the lexicon-based MWE matcher.

These tests do not need a Flask app context or DB — the matcher
operates on plain token dicts.
"""

from zeeguu.core.mwe.lexicon_matcher import (
    LexiconMatcher,
    merge_lexicon_with_stanza,
)


def _tok(text, pos="NOUN"):
    return {"text": text, "pos": pos}


def test_danish_pa_jagt_efter_is_matched_as_single_mwe():
    # Trump er på jagt efter aftale  →  "på jagt efter" is one MWE
    tokens = [
        _tok("Trump", "PROPN"),
        _tok("er", "AUX"),
        _tok("på", "ADP"),
        _tok("jagt", "NOUN"),
        _tok("efter", "ADP"),
        _tok("aftale", "NOUN"),
    ]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1
    g = groups[0]
    assert g["type"] == "lexicon"
    assert g["head_idx"] == 2
    assert sorted([g["head_idx"], *g["dependent_indices"]]) == [2, 3, 4]


def test_longest_match_wins():
    # "på vej" vs "på vej til" → longer wins
    tokens = [_tok("Han", "PRON"), _tok("er", "AUX"),
              _tok("på"), _tok("vej"), _tok("til"), _tok("byen")]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1
    assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [2, 3, 4]


def test_no_match_returns_empty():
    tokens = [_tok("Hej"), _tok("verden")]
    assert LexiconMatcher("da").detect(tokens) == []


def test_unknown_language_returns_empty():
    tokens = [_tok("på"), _tok("jagt"), _tok("efter"), _tok("aftale")]
    assert LexiconMatcher("zz").detect(tokens) == []


def test_case_insensitive_match():
    # Sentence-initial capitalization
    tokens = [_tok("På"), _tok("Jagt"), _tok("Efter"), _tok("aftalen")]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1


def test_lexicon_wins_over_stanza_when_spans_overlap():
    # Stanza might have grouped only "på jagt" (idx 2,3).
    # Lexicon catches "på jagt efter" (idx 2,3,4). Stanza dropped.
    stanza_groups = [
        {"head_idx": 3, "dependent_indices": [2], "type": "article_noun"}
    ]
    lexicon_groups = [
        {"head_idx": 2, "dependent_indices": [3, 4], "type": "lexicon"}
    ]
    merged = merge_lexicon_with_stanza(stanza_groups, lexicon_groups)
    assert len(merged) == 1
    assert merged[0]["type"] == "lexicon"


def test_non_overlapping_stanza_group_is_preserved():
    # Stanza groups idx 0,1 (e.g., aux verb).
    # Lexicon catches idx 4,5,6. Both kept.
    stanza_groups = [
        {"head_idx": 1, "dependent_indices": [0], "type": "aux_verb"}
    ]
    lexicon_groups = [
        {"head_idx": 4, "dependent_indices": [5, 6], "type": "lexicon"}
    ]
    merged = merge_lexicon_with_stanza(stanza_groups, lexicon_groups)
    assert len(merged) == 2


def test_english_in_spite_of():
    tokens = [_tok("She"), _tok("came"), _tok("in"), _tok("spite"),
              _tok("of"), _tok("rain")]
    groups = LexiconMatcher("en").detect(tokens)
    assert len(groups) == 1
    assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [2, 3, 4]


def test_punctuation_does_not_break_match_when_absent():
    # Sanity: ordinary contiguous match still works (no punct in span)
    tokens = [_tok("i"), _tok("stand"), _tok("til"), _tok("at"), _tok("gå")]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1
    assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [0, 1, 2]
