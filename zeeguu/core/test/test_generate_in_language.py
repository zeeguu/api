"""
Re-asking the LLM when it answered in the wrong language.

The detection is tested next door in test_language_check; these are about the
loop: one call when the answer is good, a second naming the mistake when it is
not, and a raise carrying enough for the call site to decide what to salvage.
"""

import pytest

from zeeguu.core.language.generate_in_language import (
    LanguageMismatchError,
    generate_in_language,
)

DANISH = (
    "Regeringen har i dag fremlagt et nyt forslag om klimaet. Forslaget skal "
    "gøre det billigere at køre i elbil, og det skal samtidig blive dyrere at "
    "flyve inden for landets grænser."
)

ENGLISH = (
    "The government presented a new proposal about the climate today. The plan "
    "would make it cheaper to drive an electric car, and at the same time more "
    "expensive to fly within the country."
)


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
