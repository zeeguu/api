import json

from zeeguu.core.llm_services.translation_validator import TranslationValidator

SENTENCE = "Jeg lærte, hvad det vil sige at gå, da jeg så evnen forsvinde"


def reply(**fields):
    return {
        "card_in_sentence": "",
        "card_reads_right": True,
        "reason": "",
        "verdict": "VALID",
        "corrected_word": "",
        "corrected_translation": "",
        "correction_in_sentence": "",
        "correction_reads_right": False,
        "frequency": "common",
        "cefr": "A2",
        "phrase_type": "collocation",
        "explanation": "",
        "literal_meaning": "",
        "dictionary_word": "",
        "dictionary_translation": "",
        **fields,
    }


# The 13 Aug 2026 case: the reply writes "what it mean to walk", judges it
# wrong, and keeps "mean" on the card anyway.
MEAN_THAT_DOES_NOT_FIT = reply(
    card_in_sentence="I learned what it will say to walk when I saw the ability disappear",
    card_reads_right=False,
    verdict="FIX",
    corrected_word="vil sige",
    corrected_translation="mean",
    correction_in_sentence="I learned what it mean to walk when I saw the ability disappear",
    correction_reads_right=False,
)
MEANS = reply(
    card_in_sentence="I learned what it will say to walk when I saw the ability disappear",
    card_reads_right=False,
    verdict="FIX",
    corrected_word="vil sige",
    corrected_translation="means",
    correction_in_sentence="I learned what it means to walk when I saw the ability disappear",
    correction_reads_right=True,
)


def validator_replying(*replies):
    # skip __init__ (needs an API key); answer each call with the next reply
    v = object.__new__(TranslationValidator)
    asked = []

    def ask(prompt, schema):
        asked.append(prompt)
        return TranslationValidator._parse_response(json.dumps(replies[len(asked) - 1]))

    v._ask = ask
    return v, asked


def parse(**fields):
    return TranslationValidator._parse_response(json.dumps(reply(**fields)))


def test_unresolved_is_neither_valid_nor_a_fix():
    r = parse(verdict="UNRESOLVED", corrected_word="umanned", corrected_translation="unmanned")
    assert r.is_unresolved and not r.is_valid
    assert r.corrected_word is None and r.corrected_translation is None


def test_a_valid_card_that_does_not_read_right_is_a_misfit():
    r = parse(card_in_sentence="I learned what it mean to walk", card_reads_right=False)
    assert TranslationValidator._misfit(r, "mean")


def test_a_correction_the_sentence_does_not_say_is_a_misfit():
    # right form in the sentence, wrong form on the card
    r = parse(
        verdict="FIX",
        corrected_translation="mean",
        correction_in_sentence="I learned what it means to walk",
        correction_reads_right=True,
    )
    assert TranslationValidator._misfit(r, "will say")


def test_a_correction_that_fits_is_not_a_misfit():
    assert not TranslationValidator._misfit(TranslationValidator._parse_response(json.dumps(MEANS)), "will say")


def test_a_misfit_is_asked_about_again():
    v, asked = validator_replying(MEAN_THAT_DOES_NOT_FIT, MEANS)

    r = v.validate_and_classify("vil sige", "will say", SENTENCE, "da", "en")

    assert len(asked) == 2
    assert "what it mean to walk" in asked[1]
    assert (r.corrected_word, r.corrected_translation) == ("vil sige", "means")


def test_a_card_that_still_does_not_fit_is_given_up_on():
    v, asked = validator_replying(MEAN_THAT_DOES_NOT_FIT, MEAN_THAT_DOES_NOT_FIT)

    r = v.validate_and_classify("vil sige", "will say", SENTENCE, "da", "en")

    assert len(asked) == 2
    assert r.is_unresolved and not r.is_valid
    assert r.corrected_translation is None
