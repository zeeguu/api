"""One typeable translation per flashcard. Cases are real prod meanings."""

import json
from types import SimpleNamespace

import pytest

from zeeguu.core.llm_services.single_translation import lists_options, pick_one
from zeeguu.core.llm_services.translation_validator import TranslationValidator


@pytest.mark.parametrize(
    "word, translation, one",
    [
        ("som skal", "which must/which should", "which must"),
        ("ved at", "by (doing something)", "by"),
        ("pour autant", "nevertheless/for all that", "nevertheless"),
        ("Ha fatto", "he did / he made", "he did"),
        ("your", "твій/твоя/твоє/твої", "твій"),
        ("Lupin", "lupine (peulvrucht)", "lupine"),
        ("s'entourer", "zich omringen (met)", "zich omringen"),
    ],
)
def test_options_are_reduced_to_one(word, translation, one):
    assert lists_options(translation, word)
    assert pick_one(translation, word) == one


@pytest.mark.parametrize(
    "word, translation",
    [
        ("09/10/2024", "09/10/2024"),  # a date
        ("roll-on/roll-off", "roll-on/roll-off"),  # the source has the slash
        ("Mannheim/Heidelberg", "Mannheim / Heidelberg"),
        ("Einwanderungsbehörde ICE", "Immigration and Customs Enforcement (ICE)"),  # gloss is in the source
        ("hund", "dog"),
        ("", ""),
    ],
)
def test_legitimate_translations_are_left_alone(word, translation):
    assert not lists_options(translation, word)
    assert pick_one(translation, word) == translation


def test_nothing_left_after_dropping_keeps_the_original():
    assert pick_one("(something)", "noget") == "(something)"


def test_slashes_between_digits_are_not_alternatives():
    assert pick_one("24/7 service/support", "døgnservice") == "24/7 service"


def test_a_gloss_counts_as_in_the_source_only_by_whole_words():
    assert lists_options("book(s)", "Bücher")
    assert pick_one("book(s)", "Bücher") == "book"
    assert pick_one("dog ()", "hund") == "dog"  # an empty gloss is no exemption


def test_the_source_exempts_only_its_own_segments():
    assert pick_one("roll-on/roll-off ferry/boat", "roll-on/roll-off") == "roll-on/roll-off ferry"
    assert pick_one("far (to) (away)", "lointains (à)") == "far (to)"


@pytest.mark.parametrize(
    "word, translation",
    [
        ("12-talspigerne m/k", "The 12s girls m / f"),
        ("som/være", "as / be"),
        ("(Prellung)", "(Blauwe plek)"),
        ("lointains (à)", "ver (naar)"),
    ],
)
def test_the_translation_of_the_sources_own_segments_is_not_an_option(word, translation):
    assert not lists_options(translation, word)


class FakeClient:
    """Answers with the given replies in order; records the prompts."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []
        self.messages = self

    def create(self, messages, **_):
        self.prompts.append(messages[0]["content"])
        if isinstance(self.replies[0], Exception):
            raise self.replies.pop(0)
        reply = {
            "reason": "",
            "verdict": "VALID",
            "corrected_word": "",
            "corrected_translation": "",
            "frequency": "common",
            "cefr": "A2",
            "phrase_type": "collocation",
            "explanation": "",
            "literal_meaning": "",
            **self.replies.pop(0),
        }
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(reply))])


def validate(client, word, translation):
    validator = object.__new__(TranslationValidator)  # __init__ needs an API key
    validator.client = client
    return validator.validate_and_classify(word, translation, "Han har breve som skal sendes i dag.", "da", "en")


def test_a_fix_that_lists_options_is_asked_again():
    client = FakeClient(
        {"verdict": "FIX", "corrected_translation": "which must/which should"},
        {"verdict": "FIX", "corrected_translation": "which must"},
    )
    result = validate(client, "som skal", "will")
    assert len(client.prompts) == 2 and "which must/which should" in client.prompts[1]
    assert (result.is_valid, result.corrected_translation) == (False, "which must")


def test_an_old_translation_with_options_is_not_waved_through_as_valid():
    client = FakeClient({"verdict": "VALID"}, {"verdict": "VALID"})
    result = validate(client, "som skal", "which must/which should")
    assert len(client.prompts) == 2
    assert (result.is_valid, result.corrected_translation) == (False, "which must")


def test_a_clean_answer_costs_one_call():
    client = FakeClient({"verdict": "VALID"})
    result = validate(client, "hund", "dog")
    assert len(client.prompts) == 1 and result.is_valid


def test_a_failed_retry_keeps_the_first_reply_and_its_classification():
    client = FakeClient(
        {"verdict": "FIX", "corrected_translation": "which must/which should", "cefr": "B1"},
        TimeoutError("retry timed out"),
    )
    result = validate(client, "som skal", "will")
    assert (result.is_valid, result.corrected_translation, result.cefr_level) == (False, "which must", "B1")


def test_a_translation_that_cannot_be_reduced_is_not_turned_into_a_fix():
    client = FakeClient({"verdict": "VALID"}, {"verdict": "VALID"})
    result = validate(client, "noget", "(something)")
    assert result.is_valid and result.corrected_translation is None


def test_a_fix_of_the_word_alone_still_checks_the_kept_translation():
    client = FakeClient(
        {"verdict": "FIX", "corrected_word": "som skal"},
        {"verdict": "FIX", "corrected_word": "som skal"},
    )
    result = validate(client, "skal", "which must/which should")
    assert len(client.prompts) == 2
    assert (result.corrected_word, result.corrected_translation) == ("som skal", "which must")

