from types import SimpleNamespace

from zeeguu.core.llm_services import translation_validator
from zeeguu.core.llm_services.translation_validator import TranslationValidator
from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.model.meaning import Meaning


def failing_validator():
    # skip __init__ (needs an API key); every call raises, as on 28 Sep 2026
    v = object.__new__(TranslationValidator)

    def create(**kwargs):
        raise TypeError("Messages.create() got an unexpected keyword argument 'temperature'")

    v.client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return v


def test_an_api_error_is_no_verdict_and_goes_to_sentry(monkeypatch):
    reported = []
    monkeypatch.setattr("sentry_sdk.capture_exception", reported.append)

    result = failing_validator().validate_and_classify("noget", "one", "noget af det", "da", "en")

    assert result is None
    assert len(reported) == 1


def test_no_verdict_leaves_the_word_unvalidated(monkeypatch):
    monkeypatch.setattr("sentry_sdk.capture_exception", lambda e: None)
    monkeypatch.setattr(translation_validator, "TranslationValidator", failing_validator)

    phrase = lambda text, code: SimpleNamespace(content=text, language=SimpleNamespace(code=code))
    meaning = SimpleNamespace(
        validated=Meaning.NOT_VALIDATED, origin=phrase("noget", "da"), translation=phrase("one", "en")
    )
    user_word = SimpleNamespace(
        id=1, meaning=meaning, preferred_bookmark=SimpleNamespace(get_context=lambda: "noget af det")
    )

    assert UserWordValidationService.validate_and_fix(None, user_word) is user_word
    assert meaning.validated == Meaning.NOT_VALIDATED
