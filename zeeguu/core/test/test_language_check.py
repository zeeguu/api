"""
Unit tests for the shared LLM output-language check.

The question it asks is "is this plausibly Danish?", not "which language is this?".
That is what lets it drop the hand-maintained list of confusable languages the
first version needed, and these tests pin both halves of that: a text that also
looks like its neighbour still passes, and a text in the neighbour's language does
not.

No Flask app context or DB — the check works on raw text.
"""

from zeeguu.core.language.language_check import (
    MIN_CHARS_TO_JUDGE,
    SENTENCE_LEVEL_FLOOR,
    _detectable_text,
    field_mismatches,
    language_mismatch,
    plausibility,
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


def test_the_gap_between_right_and_wrong_is_wide():
    # The whole design rests on this: sound text scores far above the floor and
    # wrong-language text far below, so the floor's exact value is not delicate.
    assert plausibility(DANISH, "da") > 0.5
    assert plausibility(ENGLISH, "da") < 0.05
    assert SENTENCE_LEVEL_FLOOR < 0.5


def test_correct_text_scores_high_enough_that_neighbours_never_come_up():
    # The confusable-family list existed to answer "is Norwegian close enough to
    # Danish?". Asking about Danish directly never poses it: correct Danish is
    # plausible Danish by a wide margin, whatever else it resembles.
    assert plausibility(DANISH, "da") > 0.5


def test_a_neighbouring_language_is_not_excused():
    # And the list's cost is gone with it. Given a paragraph, Danish is decisively
    # not Norwegian, so a Norwegian learner served Danish is now caught — the old
    # family list waved this through.
    assert plausibility(DANISH, "no") < SENTENCE_LEVEL_FLOOR
    assert language_mismatch(DANISH, "no").detected == "da"


def test_a_further_language_is_caught_too():
    assert language_mismatch(GERMAN, "da").detected == "de"


def test_too_short_to_judge_alone_is_not_a_mismatch():
    # "Can't judge" is a distinct answer from "wrong". A field is checked on its own
    # with nothing to average against, so short text answers None — correct Danish
    # this short scores under the floor, and flagging it would be noise.
    assert len(_detectable_text("Hej med dig")) < MIN_CHARS_TO_JUDGE
    assert not language_mismatch("Hej med dig", "da")


def test_a_language_with_no_model_is_skipped():
    # Zeeguu offers Kurdish; lingua has no Kurdish. We cannot check it, so we don't.
    assert plausibility(DANISH, "ku") is None
    assert not language_mismatch(ENGLISH, "ku")


def test_html_markup_does_not_hide_the_language():
    assert language_mismatch(f"<p>{ENGLISH}</p>", "da").detected == "en"
    assert not language_mismatch(f"<p>{DANISH}</p>", "da")


def test_prose_with_angle_brackets_is_not_eaten_as_markup():
    # An unanchored tag pattern turned "Hvis 5 < 10 og 20 > 15" into "Hvis 5 15",
    # deleting the very text we are about to judge.
    kept = _detectable_text("Hvis 5 < 10 og 20 > 15, saa er tallene rigtige.")
    assert "10 og 20" in kept
    assert _detectable_text("<p>Hej <strong>med</strong> dig</p>") == "Hej med dig"


def test_field_mismatches_reports_one_per_wrong_field():
    mismatches = field_mismatches([("A1", DANISH), ("A2", ENGLISH), ("B1", GERMAN)], "da")
    assert [m.label for m in mismatches] == ["A2", "B1"]
