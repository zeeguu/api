"""
Unit tests for the shared LLM output-language check.

No Flask app context or DB — the check works on raw text.
"""

import pytest

from zeeguu.core.language.language_check import (
    LanguageMismatchError,
    field_mismatches,
    language_mismatch,
    passage_mismatch,
    generate_in_language,
    language_code_of,
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
    assert language_mismatch(DANISH, "da") is None


def test_text_in_another_language_is_caught():
    mismatch = language_mismatch(ENGLISH, "da", label="summary")
    assert mismatch.label == "summary"
    assert mismatch.expected == "da"
    assert mismatch.detected == "en"


def test_confusable_neighbours_are_not_flagged_against_each_other():
    # langdetect regularly reads Danish as Norwegian; that must not fail a text.
    assert language_mismatch(DANISH, "no") is None


def test_too_short_to_judge_is_not_a_mismatch():
    # "Can't judge" is a distinct answer from "wrong" — titles live down here.
    assert language_mismatch("Hej med dig", "da") is None


def test_language_langdetect_cannot_check_is_skipped():
    # Kurdish has no langdetect profile; we can't check it, so we don't block on it.
    assert language_mismatch(ENGLISH, "ku") is None


def test_html_markup_does_not_hide_the_language():
    html = f"<p>{ENGLISH}</p><p><strong>More</strong> of the same.</p>"
    assert language_mismatch(html, "da").detected == "en"
    assert language_mismatch(f"<p>{DANISH}</p>", "da") is None


def test_field_mismatches_reports_one_per_wrong_field():
    mismatches = field_mismatches(
        [("A1", DANISH), ("A2", ENGLISH), ("B1", GERMAN)], "da"
    )
    assert [m.label for m in mismatches] == ["A2", "B1"]


def test_a_wrong_language_half_is_caught_even_when_the_whole_reads_right():
    # The audio-lesson failure: an all-English first half followed by correct
    # Danish scores mostly-Danish as one blob and would otherwise pass.
    pieces = ENGLISH.split(". ") + DANISH.split(". ") + DANISH.split(". ")
    assert passage_mismatch(pieces, "da") is not None


def test_a_single_foreign_sentence_does_not_fail_a_good_passage():
    pieces = DANISH.split(". ") * 3 + ["The minister was not available for comment."]
    assert passage_mismatch(pieces, "da") is None


def test_language_code_of_accepts_codes_names_and_language_objects():
    class FakeLanguage:
        code = "da"

    assert language_code_of("da") == "da"
    assert language_code_of("Danish") == "da"
    assert language_code_of(FakeLanguage()) == "da"


def test_generate_in_language_returns_a_good_first_attempt_without_retrying():
    calls = []

    def generate(correction):
        calls.append(correction)
        return {"text": DANISH}

    result = generate_in_language(
        generate, "da", lambda r: [("text", r["text"])], "test"
    )
    assert result == {"text": DANISH}
    assert calls == [""]


def test_generate_in_language_retries_with_a_correction_naming_the_problem():
    calls = []
    answers = [{"text": ENGLISH}, {"text": DANISH}]

    def generate(correction):
        calls.append(correction)
        return answers[len(calls) - 1]

    result = generate_in_language(
        generate, "da", lambda r: [("text", r["text"])], "test"
    )
    assert result == {"text": DANISH}
    assert calls[0] == ""
    assert "Danish" in calls[1] and "en" in calls[1]


def test_generate_in_language_gives_up_carrying_the_last_result():
    def generate(correction):
        return {"assessment": "B1", "text": ENGLISH}

    with pytest.raises(LanguageMismatchError) as caught:
        generate_in_language(generate, "da", lambda r: [("text", r["text"])], "test")

    # The last result rides along so a caller can keep the parts that are fine.
    assert caught.value.result["assessment"] == "B1"
    assert [m.label for m in caught.value.mismatches] == ["text"]
