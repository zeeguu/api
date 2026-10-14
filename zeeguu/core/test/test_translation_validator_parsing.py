import json

from zeeguu.core.llm_services.translation_validator import TranslationValidator


def parse(**fields):
    reply = {
        "reason": "",
        "verdict": "VALID",
        "corrected_word": "",
        "corrected_translation": "",
        "frequency": "common",
        "cefr": "A1",
        "phrase_type": "single_word",
        "explanation": "",
        "literal_meaning": "",
        **fields,
    }
    # _parse_response uses no instance state; skip __init__ (needs an API key)
    return TranslationValidator._parse_response(object.__new__(TranslationValidator), json.dumps(reply))


def test_valid_is_classified_and_empty_fields_are_none():
    r = parse(reason="'hund' is plainly 'dog'")
    assert r.is_valid
    assert (r.frequency, r.cefr_level, r.phrase_type) == ("common", "A1", "single_word")
    assert r.explanation is None and r.literal_meaning is None


def test_fix_carries_the_correction():
    r = parse(
        verdict="FIX",
        corrected_word="noget af",
        corrected_translation="one of",
        cefr="B1",
        phrase_type="collocation",
        reason="'noget' alone means 'something'",
        literal_meaning="something of",
    )
    assert not r.is_valid
    assert (r.corrected_word, r.corrected_translation) == ("noget af", "one of")
    assert r.literal_meaning == "something of"


def test_valid_ignores_stray_correction_fields():
    # a VALID verdict must not move the bookmark, whatever else was filled in
    r = parse(corrected_word="hund", corrected_translation="dog")
    assert r.is_valid and r.corrected_word is None and r.corrected_translation is None


def test_leftover_unicode_escapes_become_letters():
    # the model's JSON held "\\u0153", which json.loads turns into the text œ, not œ
    r = parse(verdict="FIX", corrected_word="main-d'\\u0153uvre", corrected_translation="arbeidskrachten")
    assert r.corrected_word == "main-d'œuvre"
    assert parse(verdict="FIX", corrected_word="l'\\u00e9poque").corrected_word == "l'époque"
