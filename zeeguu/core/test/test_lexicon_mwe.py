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


# ─── Lemma-headed matching ──────────────────────────────────────────────
#
# The bug these pin: "Forskerne fandt ud af, at ..." was grouped as "ud af"
# and translated "out of". The dependency parser had it right -- it attached
# "ud" to "fandt" -- but GermanicStrategy only turns ADV+advmod into a group
# for negation words, so it emitted nothing, and the lexicon entry "ud af"
# filled the gap with a span that is not an expression.
#
# Lemmas below are the ones Stanza's da/ddt models actually produce; they were
# read off the pipeline rather than guessed.


def _ltok(text, lemma, pos="NOUN"):
    return {"text": text, "pos": pos, "lemma": lemma}


def test_inflected_verb_mwe_beats_shorter_surface_entry():
    # Forskerne fandt ud af, at ...  ->  "fandt ud af", not "ud af"
    tokens = [
        _ltok("Forskerne", "forsker", "NOUN"),
        _ltok("fandt", "finde", "VERB"),
        _ltok("ud", "ud", "ADV"),
        _ltok("af", "af", "ADP"),
        _ltok(",", ",", "PUNCT"),
        _ltok("at", "at", "SCONJ"),
    ]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1
    g = groups[0]
    assert g["head_idx"] == 1
    assert sorted(g["dependent_indices"]) == [2, 3]


def test_every_inflection_of_the_verb_reaches_the_same_entry():
    # fandt / finde / fundet all lemmatise to "finde".
    for surface in ["fandt", "finde", "fundet"]:
        tokens = [
            _ltok(surface, "finde", "VERB"),
            _ltok("ud", "ud", "ADV"),
            _ltok("af", "af", "ADP"),
            _ltok("sandheden", "sandhed", "NOUN"),
        ]
        groups = LexiconMatcher("da").detect(tokens)
        assert len(groups) == 1, surface
        assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [0, 1, 2]


def test_light_verb_entries_now_match_when_conjugated():
    # These were in the lexicon all along but only matched in the infinitive,
    # which is the one form a reader almost never meets.
    tokens = [
        _ltok("Jeg", "jeg", "PRON"),
        _ltok("har", "have", "VERB"),
        _ltok("brug", "brug", "NOUN"),
        _ltok("for", "for", "ADP"),
        _ltok("hjælp", "hjælp", "NOUN"),
    ]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1
    assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [1, 2, 3]


def test_frozen_phrase_is_not_lemma_matched():
    # "i dagene efter" is "in the days after"; "dagene" lemmatises to "dag",
    # so a blanket lemma match would group it as "i dag" (today). The surface
    # set must stay surface-only.
    tokens = [
        _ltok("syg", "syg", "ADJ"),
        _ltok("i", "i", "ADP"),
        _ltok("dagene", "dag", "NOUN"),
        _ltok("efter", "efter", "ADV"),
    ]
    assert LexiconMatcher("da").detect(tokens) == []


def test_tail_is_not_lemmatised():
    # "nødt" lemmatises to "nød", so lemmatising the whole span would miss
    # "være nødt til" entirely. Only the head is lemmatised.
    tokens = [
        _ltok("Han", "han", "PRON"),
        _ltok("var", "være", "AUX"),
        _ltok("nødt", "nød", "ADJ"),
        _ltok("til", "til", "ADP"),
    ]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1
    assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [1, 2, 3]


def test_language_without_a_verb_lexicon_still_matches_surface_entries():
    # Lemma-headed matching is per-language and opt-in. A language that has
    # not opted in must keep working exactly as before -- asserted on
    # behaviour rather than on which languages are currently enabled, so
    # switching on no/sv/en does not fail this test.
    matcher = LexiconMatcher("de")
    assert not matcher.verb_lexicon
    tokens = [
        _ltok("Er", "er", "PRON"),
        _ltok("handelte", "handeln", "VERB"),
        _ltok("im", "im", "ADP"),
        _ltok("Hinblick", "Hinblick", "NOUN"),
        _ltok("auf", "auf", "ADP"),
        _ltok("Kosten", "Kosten", "NOUN"),
    ]
    groups = matcher.detect(tokens)
    assert len(groups) == 1
    assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [2, 3, 4]


def test_lemma_headed_match_requires_a_verbal_head():
    # Danish "have" is both "to have" and "garden", so "haven" ("the garden")
    # lemmatises straight onto the entry "have brug for". The POS tag is what
    # separates them.
    noun_head = [
        _ltok("haven", "have", "NOUN"),
        _ltok("brug", "brug", "NOUN"),
        _ltok("for", "for", "ADP"),
    ]
    assert LexiconMatcher("da").detect(noun_head) == []

    verb_head = [
        _ltok("havde", "have", "VERB"),
        _ltok("brug", "brug", "NOUN"),
        _ltok("for", "for", "ADP"),
    ]
    assert len(LexiconMatcher("da").detect(verb_head)) == 1


def test_danish_has_opted_in():
    assert LexiconMatcher("da").verb_lexicon


def test_matcher_works_without_lemmas():
    # Callers that skip the lemmatiser still get surface matching.
    tokens = [
        {"text": "på", "pos": "ADP"},
        {"text": "grund", "pos": "NOUN"},
        {"text": "af", "pos": "ADP"},
        {"text": "vejret", "pos": "NOUN"},
    ]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1
    assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [0, 1, 2]


def test_lemmatiser_miss_is_patched_by_a_surface_entry():
    # "læg" lemmatises to "læge" (doctor), so the imperative never reaches the
    # verb entry "lægge mærke til". It is listed as a literal instead -- the
    # two sets compose, which is why one lemmatiser miss does not argue for
    # enumerating every inflected form by hand.
    tokens = [
        _ltok("Læg", "læge", "VERB"),
        _ltok("mærke", "mærke", "NOUN"),
        _ltok("til", "til", "ADP"),
        _ltok("hende", "hun", "PRON"),
    ]
    groups = LexiconMatcher("da").detect(tokens)
    assert len(groups) == 1
    assert sorted([groups[0]["head_idx"], *groups[0]["dependent_indices"]]) == [0, 1, 2]


# ─── Extending a lexicon span over the grammar attached to its verb ─────
#
# A Stanza group sharing a token with a lexicon span is usually the same verb
# wearing its grammar. Dropping it left the auxiliary, the negation or the
# infinitive marker outside any group -- a tap on "ikke" gave "not" rather than
# "could not figure out". All three shapes below were found in production, in
# the level-adapted summaries, on 2026-09-27.


def _merge(stanza_groups, lexicon_groups, tokens=None):
    return merge_lexicon_with_stanza(stanza_groups, lexicon_groups, tokens)


def _span(group):
    return sorted({group["head_idx"], *group["dependent_indices"]})


def test_infinitive_marker_is_absorbed():
    # "at finde ud af": parser has [at finde], lexicon has [finde ud af]
    merged = _merge(
        [{"head_idx": 1, "dependent_indices": [0], "type": "grammatical"}],
        [{"head_idx": 1, "dependent_indices": [2, 3], "type": "lexicon"}],
    )
    assert len(merged) == 1
    assert _span(merged[0]) == [0, 1, 2, 3]


def test_perfect_auxiliary_is_absorbed():
    # "har fundet ud af"
    merged = _merge(
        [{"head_idx": 1, "dependent_indices": [0], "type": "aux_verb"}],
        [{"head_idx": 1, "dependent_indices": [2, 3], "type": "lexicon"}],
    )
    assert len(merged) == 1
    assert _span(merged[0]) == [0, 1, 2, 3]


def test_modal_and_negation_are_absorbed():
    # "kunne ikke finde ud af"
    merged = _merge(
        [{"head_idx": 2, "dependent_indices": [0, 1], "type": "negation"}],
        [{"head_idx": 2, "dependent_indices": [3, 4], "type": "lexicon"}],
    )
    assert len(merged) == 1
    assert _span(merged[0]) == [0, 1, 2, 3, 4]


def test_non_overlapping_groups_are_both_kept():
    # "på jagt efter en aftale": the article+noun group shares no token with
    # the idiom, so neither is touched.
    merged = _merge(
        [{"head_idx": 5, "dependent_indices": [4], "type": "article_noun"}],
        [{"head_idx": 0, "dependent_indices": [1, 2], "type": "lexicon"}],
    )
    assert len(merged) == 2
    assert sorted(_span(g) for g in merged) == [[0, 1, 2], [4, 5]]


def test_a_group_that_reaches_too_far_is_not_absorbed():
    # The safety rail. A separated particle verb can span half a sentence
    # ("Han steht jeden Morgen um sechs Uhr auf"). Merging one of those would
    # swallow everything between, so when the union is not contiguous the old
    # behaviour stands and the parser group is dropped.
    merged = _merge(
        [{"head_idx": 0, "dependent_indices": [9], "type": "particle_verb"}],
        [{"head_idx": 0, "dependent_indices": [1, 2], "type": "lexicon"}],
    )
    assert len(merged) == 1
    assert merged[0]["type"] == "lexicon"
    assert _span(merged[0]) == [0, 1, 2]


def test_punctuation_does_not_block_absorption():
    # "fandt ud af, at ..." -- a comma inside the union is not a gap.
    tokens = [
        _ltok("Han", "han", "PRON"),
        _ltok("har", "have", "AUX"),
        _ltok("fundet", "finde", "VERB"),
        _ltok("ud", "ud", "ADV"),
        _ltok(",", ",", "PUNCT"),
        _ltok("af", "af", "ADP"),
    ]
    merged = _merge(
        [{"head_idx": 2, "dependent_indices": [1], "type": "aux_verb"}],
        [{"head_idx": 2, "dependent_indices": [3, 5], "type": "lexicon"}],
        tokens,
    )
    assert len(merged) == 1
    assert _span(merged[0]) == [1, 2, 3, 5]


def test_lexicon_groups_are_not_mutated_in_place():
    # The caller's list is reused elsewhere; merging must not edit it.
    lexicon = [{"head_idx": 1, "dependent_indices": [2, 3], "type": "lexicon"}]
    _merge([{"head_idx": 1, "dependent_indices": [0], "type": "aux_verb"}], lexicon)
    assert lexicon[0]["dependent_indices"] == [2, 3]
