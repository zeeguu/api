"""
Unit tests for the shared LLM output-language check.

No Flask app context or DB — the check works on raw text.
"""

import pytest

from zeeguu.core.language.language_check import (
    _detectable_text,
    field_mismatches,
    language_mismatch,
    passage_mismatch,
)

DANISH = (
    "Regeringen har i dag fremlagt et nyt forslag om klimaet. Forslaget skal "
    "gøre det billigere at køre i elbil, og det skal samtidig blive dyrere at "
    "flyve inden for landets grænser. Flere partier har allerede sagt, at de "
    "bakker op om planen."
)

ENGLISH = (
    "The government presented a new proposal about the climate today. The plan "
    "would make it cheaper to drive an electric car, and at the same time more "
    "expensive to fly within the country. Several parties have already said "
    "they support the plan."
)

GERMAN = (
    "Die Regierung hat heute einen neuen Vorschlag zum Klima vorgelegt. Der "
    "Plan soll es billiger machen, ein Elektroauto zu fahren, und gleichzeitig "
    "teurer, innerhalb des Landes zu fliegen."
)


def test_text_in_the_expected_language_passes():
    assert not language_mismatch(DANISH, "da")


def test_text_in_another_language_is_caught():
    mismatch = language_mismatch(ENGLISH, "da", label="summary")
    assert mismatch.label == "summary"
    assert mismatch.expected == "da"
    assert mismatch.detected == "en"


def test_confusable_neighbours_are_not_flagged_against_each_other():
    # langdetect regularly reads Danish as Norwegian; that must not fail a text.
    assert not language_mismatch(DANISH, "no")


def test_too_short_to_judge_is_not_a_mismatch():
    # "Can't judge" is a distinct answer from "wrong" — titles live down here.
    assert not language_mismatch("Hej med dig", "da")


def test_language_langdetect_cannot_check_is_skipped():
    # Kurdish has no langdetect profile; we can't check it, so we don't block on it.
    assert not language_mismatch(ENGLISH, "ku")


def test_html_markup_does_not_hide_the_language():
    html = f"<p>{ENGLISH}</p><p><strong>More</strong> of the same.</p>"
    assert language_mismatch(html, "da").detected == "en"
    assert not language_mismatch(f"<p>{DANISH}</p>", "da")


def test_field_mismatches_reports_one_per_wrong_field():
    mismatches = field_mismatches(
        [("A1", DANISH), ("A2", ENGLISH), ("B1", GERMAN)], "da"
    )
    assert [m.label for m in mismatches] == ["A2", "B1"]


def test_a_wrong_language_half_is_caught_even_when_the_whole_reads_right():
    # The audio-lesson failure: an all-English first half followed by correct
    # Danish scores mostly-Danish as one blob and would otherwise pass.
    pieces = ENGLISH.split(". ") + DANISH.split(". ") + DANISH.split(". ")
    assert passage_mismatch(pieces, "da")


def test_a_single_foreign_sentence_does_not_fail_a_good_passage():
    pieces = DANISH.split(". ") * 3 + ["The minister was not available for comment."]
    assert not passage_mismatch(pieces, "da")


def test_prose_with_angle_brackets_is_not_eaten_as_markup():
    # An unanchored tag pattern turned "Hvis 5 < 10 og 20 > 15" into "Hvis 5 15",
    # deleting the very text we are about to judge.
    kept = _detectable_text("Hvis 5 < 10 og 20 > 15, saa er tallene rigtige.")
    assert "10 og 20" in kept
    assert _detectable_text("<p>Hej <strong>med</strong> dig</p>") == "Hej med dig"


def test_no_language_to_check_against_is_not_a_crash():
    assert not language_mismatch(DANISH, None)
    assert not language_mismatch(DANISH, "")


def test_a_passage_given_as_one_string_is_refused():
    # Iterating a string yields characters; the chunks read as Welsh and the
    # caller gets a confident mismatch on perfectly good text.
    with pytest.raises(TypeError):
        passage_mismatch(DANISH, "da")
    assert not passage_mismatch([DANISH], "da")
