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


def test_a_give_up_is_neither_valid_nor_a_fix():
    for verdict in ("BROKEN_SENTENCE", "WORD_NOT_FIT"):
        r = parse(verdict=verdict, corrected_word="umanned", corrected_translation="unmanned")
        assert r.gave_up == verdict and r.verdict == verdict and not r.is_valid
    assert r.corrected_word is None and r.corrected_translation is None


def test_a_valid_card_that_does_not_read_right_is_a_misfit():
    r = parse(card_in_sentence="I learned what it mean to walk", card_reads_right=False)
    assert TranslationValidator._misfit(r, "vil sige", "mean", SENTENCE)


def test_a_correction_the_sentence_does_not_say_is_a_misfit():
    # right form in the sentence, wrong form on the card
    r = parse(
        verdict="FIX",
        corrected_translation="mean",
        correction_in_sentence="I learned what it means to walk",
        correction_reads_right=True,
    )
    assert TranslationValidator._misfit(r, "vil sige", "will say", SENTENCE)


def test_a_correction_that_fits_is_not_a_misfit():
    assert not TranslationValidator._misfit(TranslationValidator._parse_response(json.dumps(MEANS)), "vil sige", "will say", SENTENCE)


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
    assert r.gave_up == "WORD_NOT_FIT" and not r.is_valid
    assert r.corrected_translation is None


def test_a_failed_retry_is_no_verdict_not_a_give_up():
    v, asked = validator_replying(MEAN_THAT_DOES_NOT_FIT)  # the second call raises

    assert v.validate_and_classify("vil sige", "will say", SENTENCE, "da", "en") is None


def test_words_of_a_correction_may_be_split_by_the_sentence():
    from zeeguu.core.llm_services.translation_validator import words_in_order

    assert words_in_order("put up for sale", "homeowners who put their homes up for sale")
    assert words_in_order("don't think", "The critics don’t think the film is good")
    assert not words_in_order("mean", "I learned what it means to walk")


def test_a_give_up_is_not_asked_again_about_options():
    # "by (doing something)" lists options; a give-up must not be re-asked into a FIX
    v, asked = validator_replying(reply(verdict="BROKEN_SENTENCE", reason="the sentence is cut off"))

    r = v.validate_and_classify("ved at", "by (doing something)", "Det ganske særl", "da", "en")

    assert len(asked) == 1 and r.gave_up == "BROKEN_SENTENCE"


def test_giving_up_leaves_the_meaning_and_takes_the_word_out_of_study(monkeypatch):
    from types import SimpleNamespace
    from zeeguu.core.llm_services import translation_validator
    from zeeguu.core.llm_services.validation_service import UserWordValidationService
    from zeeguu.core.model.meaning import Meaning

    unresolved = TranslationValidator._parse_response(json.dumps(reply(verdict="BROKEN_SENTENCE", reason="broken")))
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

    phrase = lambda text, code: SimpleNamespace(content=text, language=SimpleNamespace(code=code))
    meaning = SimpleNamespace(
        validated=Meaning.NOT_VALIDATED, origin=phrase("mennesker", "da"), translation=phrase("unmanned", "en")
    )
    user_word = SimpleNamespace(
        id=1,
        meaning=meaning,
        fit_for_study=True,
        set_unfit_for_study=lambda session: setattr(user_word, "fit_for_study", False),
        preferred_bookmark=SimpleNamespace(get_context=lambda: "Dronen er mennesker og kan flyve"),
    )
    db_session = SimpleNamespace(add=lambda x: None, commit=lambda: None)

    assert UserWordValidationService.validate_and_fix(db_session, user_word) is None
    assert meaning.validated == Meaning.NOT_VALIDATED
    assert user_word.fit_for_study is False
    assert logged == []  # validation_log records what happened to meanings; nothing did


def test_a_valid_card_its_own_sentence_does_not_say_is_a_misfit():
    # the reply wrote "means" into the sentence and judged that, for the card "mean"
    r = parse(card_in_sentence="I learned what it means to walk", card_reads_right=True)
    assert TranslationValidator._misfit(r, "vil sige", "mean", SENTENCE)
    assert not TranslationValidator._misfit(r, "vil sige", "means", SENTENCE)


def test_a_corrected_word_that_is_not_in_the_sentence_is_a_certain_misfit():
    r = parse(verdict="FIX", corrected_word="særlig", corrected_translation="special")
    misfit = TranslationValidator._misfit(r, "særl", "unusual", "Det ganske særl")
    assert misfit and misfit.certain


def test_a_card_missing_from_its_sentence_twice_is_kept():
    # a separable verb: "anrufen" is not word for word in "Ich rufe dich an"
    anrufen = reply(
        card_in_sentence="Ich rufe dich morgen an",
        card_reads_right=True,
    )
    v, asked = validator_replying(anrufen, anrufen)

    r = v.validate_and_classify("ringe op", "anrufen", "Jeg ringer dig op i morgen", "da", "de")

    assert len(asked) == 2 and r.is_valid


def test_options_are_reduced_before_the_fit_is_checked():
    # "by (doing something)" is never word for word in a sentence; reduced to "by" it fits
    by = reply(
        card_in_sentence="She remembers her mother by posting a picture",
        card_reads_right=True,
        verdict="FIX",
        corrected_word="ved at",
        corrected_translation="by",
        correction_in_sentence="She remembers her mother by posting a picture",
        correction_reads_right=True,
    )
    v, asked = validator_replying(reply(card_in_sentence="She remembers her mother by posting a picture"), by)

    r = v.validate_and_classify(
        "ved at", "by (doing something)", "Hun mindes sin mor ved at poste et billede", "da", "en"
    )

    assert len(asked) == 2  # the options retry, and no misfit retry after it
    assert (r.corrected_word, r.corrected_translation) == ("ved at", "by")


def test_a_failed_retry_after_an_uncertain_misfit_keeps_the_first_answer():
    # "anrufen" is not word for word in "Ich rufe dich an": kept, retry or not
    first = reply(card_in_sentence="Ich rufe dich morgen an", card_reads_right=True)
    v, asked = validator_replying(first)  # the retry raises

    r = v.validate_and_classify("ringe op", "anrufen", "Jeg ringer dig op i morgen", "da", "de")

    assert len(asked) == 2 and r.is_valid


def test_cutting_options_keeps_the_replys_own_judgement():
    # VALID "by (doing something)" that the reply itself said reads wrong:
    # cut to "by", it must still be checked, not pass unexamined
    wrong = reply(card_in_sentence="She remembers her mother by (doing something) a picture",
                  card_reads_right=False)
    v, asked = validator_replying(wrong, wrong, wrong)  # options retry, then fit retry

    r = v.validate_and_classify(
        "ved at", "by (doing something)", "Hun mindes sin mor ved at poste et billede", "da", "en"
    )

    assert r.gave_up == "WORD_NOT_FIT"


def test_a_give_up_from_the_options_retry_wins():
    v, asked = validator_replying(
        reply(card_in_sentence="It is quite unusual", card_reads_right=True),
        reply(verdict="BROKEN_SENTENCE", reason="the sentence is cut off"),
    )

    r = v.validate_and_classify("særl", "unusual / special", "Det ganske særl", "da", "en")

    assert r.gave_up == "BROKEN_SENTENCE" and r.corrected_translation is None


def test_giving_up_is_for_good(monkeypatch):
    from types import SimpleNamespace
    from zeeguu.core.llm_services import translation_validator
    from zeeguu.core.llm_services.validation_service import UserWordValidationService
    from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
    from zeeguu.core.bookmark_quality.fit_for_study import fit_for_study

    gave_up = TranslationValidator._parse_response(json.dumps(reply(verdict="WORD_NOT_FIT", reason="nothing fits")))
    monkeypatch.setattr(
        translation_validator, "TranslationValidator",
        lambda: SimpleNamespace(validate_translation=lambda **kw: gave_up),
    )
    phrase = lambda text, code: SimpleNamespace(content=text, language=SimpleNamespace(code=code))
    user_word = SimpleNamespace(
        id=1, fit_for_study=True, user_preference=None,
        meaning=SimpleNamespace(validated=0, origin=phrase("x", "da"), translation=phrase("y", "en")),
        set_unfit_for_study=lambda session: setattr(user_word, "fit_for_study", False),
        preferred_bookmark=SimpleNamespace(get_context=lambda: "x er her", translation_source="reading",
                                           mwe_partner_token_i=None),
    )

    UserWordValidationService.validate_and_fix(SimpleNamespace(add=lambda x: None, commit=lambda: None), user_word)

    assert user_word.user_preference == UserWordExPreference.DONT_USE_IN_EXERCISES
    # a later recompute keeps it out, even when the word passes every quality check
    monkeypatch.setattr("zeeguu.core.bookmark_quality.fit_for_study.quality_meaning", lambda uw: True)
    assert not fit_for_study(user_word)
