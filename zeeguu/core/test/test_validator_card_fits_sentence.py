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
        if len(asked) > len(replies):
            raise TimeoutError("overloaded")
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


def test_a_failed_retry_is_no_verdict_not_a_give_up():
    v, asked = validator_replying(MEAN_THAT_DOES_NOT_FIT)  # the second call raises

    assert v.validate_and_classify("vil sige", "will say", SENTENCE, "da", "en") is None


def test_words_of_a_correction_may_be_split_by_the_sentence():
    from zeeguu.core.llm_services.translation_validator import words_in_order

    assert words_in_order("put up for sale", "homeowners who put their homes up for sale")
    assert words_in_order("don't think", "The critics don’t think the film is good")
    assert not words_in_order("mean", "I learned what it means to walk")


def test_unresolved_is_not_asked_again_about_options():
    # "by (doing something)" lists options; a give-up must not be re-asked into a FIX
    v, asked = validator_replying(reply(verdict="UNRESOLVED", reason="the sentence is cut off"))

    r = v.validate_and_classify("ved at", "by (doing something)", "Det ganske særl", "da", "en")

    assert len(asked) == 1 and r.is_unresolved


def test_giving_up_leaves_the_meaning_and_takes_the_word_out_of_study(monkeypatch):
    from types import SimpleNamespace
    from zeeguu.core.llm_services import translation_validator, validation_service
    from zeeguu.core.llm_services.validation_service import UserWordValidationService
    from zeeguu.core.model.meaning import Meaning

    unresolved = TranslationValidator._parse_response(json.dumps(reply(verdict="UNRESOLVED", reason="broken")))
    monkeypatch.setattr(
        translation_validator,
        "TranslationValidator",
        lambda: SimpleNamespace(validate_translation=lambda **kw: unresolved),
    )
    logged = []
    monkeypatch.setattr(
        "zeeguu.core.model.validation_log.ValidationLog.log_invalid",
        lambda db_session, **kw: logged.append(kw),
    )
    monkeypatch.setattr(validation_service, "_engine_of", lambda user_word: None)

    phrase = lambda text, code: SimpleNamespace(content=text, language=SimpleNamespace(code=code))
    meaning = SimpleNamespace(
        validated=Meaning.NOT_VALIDATED, origin=phrase("mennesker", "da"), translation=phrase("unmanned", "en")
    )
    user_word = SimpleNamespace(
        id=1,
        meaning=meaning,
        fit_for_study=True,
        preferred_bookmark=SimpleNamespace(get_context=lambda: "Dronen er mennesker og kan flyve"),
    )
    db_session = SimpleNamespace(add=lambda x: None, commit=lambda: None)

    assert UserWordValidationService.validate_and_fix(db_session, user_word) is None
    assert meaning.validated == Meaning.NOT_VALIDATED
    assert user_word.fit_for_study is False
    assert logged[0]["reason"].startswith("[unresolved]")


def test_a_valid_card_its_own_sentence_does_not_say_is_a_misfit():
    # the reply wrote "means" into the sentence and judged that, for the card "mean"
    r = parse(card_in_sentence="I learned what it means to walk", card_reads_right=True)
    assert TranslationValidator._misfit(r, "mean")
    assert not TranslationValidator._misfit(r, "means")
