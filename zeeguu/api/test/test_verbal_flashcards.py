import importlib
import io
import os
from contextlib import contextmanager

import pytest
from werkzeug.datastructures import FileStorage

from fixtures import (
    logged_in_client as client,
    add_one_bookmark,
    add_context_types,
    add_source_types,
)


@pytest.fixture(autouse=True)
def _enable_verbal_flashcards_feature(monkeypatch):
    monkeypatch.setattr(
        "zeeguu.api.endpoints.verbal_flashcards.is_feature_enabled_for_user",
        lambda feature_name, user: feature_name == "verbal_flashcards",
    )


def _prepare_bookmark_support():
    add_context_types()
    add_source_types()


def _set_client_learned_language(client, language_code):
    from zeeguu.core.model import Language, User
    from zeeguu.core.model.db import db

    user = User.find(client.email)
    user.learned_language = Language.find_or_create(language_code)
    db.session.commit()


def _set_client_native_language(client, language_code):
    from zeeguu.core.model import Language, User
    from zeeguu.core.model.db import db

    user = User.find(client.email)
    user.native_language = Language.find_or_create(language_code)
    db.session.commit()


@pytest.fixture(autouse=True)
def _use_supported_languages_for_verbal_flashcard_endpoint_tests(request):
    if "client" not in request.fixturenames:
        return

    client_fixture = request.getfixturevalue("client")
    _set_client_learned_language(client_fixture, "da")
    _set_client_native_language(client_fixture, "en")


@contextmanager
def _asr_service_client_loaded_with_env(
    asr_service_url=None,
    asr_language_overrides=None,
    flask_debug=None,
):
    from zeeguu.core.audio_lessons import asr_service_client

    original_asr_service_url = os.environ.get("ASR_SERVICE_URL")
    original_asr_language_overrides = os.environ.get("ASR_LANGUAGE_OVERRIDES")
    original_flask_debug = os.environ.get("FLASK_DEBUG")

    def set_or_clear_env(name, value):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    try:
        set_or_clear_env("ASR_SERVICE_URL", asr_service_url)
        set_or_clear_env("ASR_LANGUAGE_OVERRIDES", asr_language_overrides)
        set_or_clear_env("FLASK_DEBUG", flask_debug)
        yield importlib.reload(asr_service_client)
    finally:
        set_or_clear_env("ASR_SERVICE_URL", original_asr_service_url)
        set_or_clear_env("ASR_LANGUAGE_OVERRIDES", original_asr_language_overrides)
        set_or_clear_env("FLASK_DEBUG", original_flask_debug)
        importlib.reload(asr_service_client)


def _set_bookmark_level(bookmark_id, level):
    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.db import db

    bookmark = Bookmark.find(bookmark_id)
    bookmark.user_word.level = level
    db.session.commit()
    return bookmark


def _create_level_3_flashcard(
    client,
    word="moder",
    translation="mother",
    from_lang="da",
    to_lang="en",
):
    from zeeguu.core.model.context_identifier import ContextIdentifier
    from zeeguu.core.model.context_type import ContextType
    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.db import db
    from fixtures import create_and_get_article
    from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA

    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    bookmark = client.post(
        f"/contribute_translation/{from_lang}/{to_lang}",
        json={
            "word": word,
            "translation": translation,
            "context": f"stellt sich {word} Präsident",
            "url": URL_SPIEGEL_VENEZUELA,
            "source_id": article["source_id"],
            "context_identifier": context_i.as_dictionary(),
        },
    )
    bookmark_id = bookmark["bookmark_id"]
    bookmark_row = Bookmark.find(bookmark_id)
    bookmark_row.user_word.level = 3
    db.session.commit()
    return bookmark_row


def test_verbal_flashcards_only_returns_level_3_plus_words_by_default(client, monkeypatch):
    monkeypatch.delenv("VERBAL_FLASHCARDS_REQUIRE_LEVEL_3", raising=False)
    _prepare_bookmark_support()

    bookmark = _create_level_3_flashcard(client)
    bookmark_id = bookmark.id
    bookmark = _set_bookmark_level(bookmark_id, 2)

    flashcards = client.get("/verbal_flashcards")
    assert flashcards["total"] == 0

    bookmark = _set_bookmark_level(bookmark_id, 3)
    expected_prompt = bookmark.user_word.meaning.translation.content
    expected_answer = bookmark.user_word.meaning.origin.content
    flashcards = client.get("/verbal_flashcards")

    assert flashcards["total"] == 1
    assert len(flashcards["flashcards"]) == 1
    assert flashcards["flashcards"][0]["id"] == str(bookmark_id)
    assert flashcards["flashcards"][0]["prompt"] == expected_prompt
    assert flashcards["flashcards"][0]["answer"] == expected_answer


def test_verbal_flashcards_returns_lower_level_words_when_experiment_override_is_set(client, monkeypatch):
    monkeypatch.setenv("VERBAL_FLASHCARDS_REQUIRE_LEVEL_3", "false")
    _prepare_bookmark_support()

    bookmark = _create_level_3_flashcard(client)
    bookmark_id = bookmark.id
    bookmark = _set_bookmark_level(bookmark_id, 1)
    expected_answer = bookmark.user_word.meaning.origin.content

    flashcards = client.get("/verbal_flashcards")

    assert flashcards["total"] == 1
    assert flashcards["flashcards"][0]["id"] == str(bookmark_id)
    assert flashcards["flashcards"][0]["answer"] == expected_answer


def test_verbal_flashcard_prompt_is_translation_and_answer_is_learned_word(client):
    _prepare_bookmark_support()

    bookmark = _create_level_3_flashcard(client, word="moder", translation="mother")
    bookmark_id = bookmark.id

    flashcards = client.get("/verbal_flashcards")

    assert flashcards["total"] == 1
    assert flashcards["flashcards"][0] == {
        "id": str(bookmark_id),
        "prompt": "mother",
        "answer": "moder",
    }


def test_verbal_flashcards_returns_404_when_feature_is_disabled(client, monkeypatch):
    _prepare_bookmark_support()

    monkeypatch.setattr(
        "zeeguu.api.endpoints.verbal_flashcards.is_feature_enabled_for_user",
        lambda feature_name, user: False,
    )

    response = client.client.get(client.append_session("/verbal_flashcards"))

    assert response.status_code == 404
    assert b"Verbal flashcards are not enabled for this user" in response.data


def test_verbal_flashcards_returns_404_when_learned_language_is_not_danish(client):
    _set_client_learned_language(client, "de")

    response = client.client.get(client.append_session("/verbal_flashcards"))

    assert response.status_code == 404
    assert b"Verbal flashcards are not enabled for this user" in response.data


def test_verbal_flashcards_rejects_unsupported_translation_language(client):
    _set_client_learned_language(client, "da")
    _set_client_native_language(client, "de")

    response = client.client.get(client.append_session("/verbal_flashcards"))

    assert response.status_code == 403
    assert b"Verbal flashcards require English or Danish translation language" in response.data


def test_verbal_flashcards_deduplicate_same_origin_word(client):
    _prepare_bookmark_support()

    _create_level_3_flashcard(client, word="moder", translation="mother")
    _create_level_3_flashcard(client, word="moder", translation="mom")

    flashcards = client.get("/verbal_flashcards")

    assert flashcards["total"] == 1
    assert flashcards["flashcards"][0]["answer"] == "moder"


def test_verbal_flashcards_paginates_results(client):
    _prepare_bookmark_support()

    _create_level_3_flashcard(client, word="moder", translation="mother")
    _create_level_3_flashcard(client, word="penge", translation="money")

    first_page = client.get("/verbal_flashcards?limit=1&offset=0")
    second_page = client.get("/verbal_flashcards?limit=1&offset=1")

    assert first_page["total"] == 2
    assert first_page["limit"] == 1
    assert first_page["offset"] == 0
    assert len(first_page["flashcards"]) == 1

    assert second_page["total"] == 2
    assert second_page["limit"] == 1
    assert second_page["offset"] == 1
    assert len(second_page["flashcards"]) == 1
    assert first_page["flashcards"][0]["id"] != second_page["flashcards"][0]["id"]


def test_sanitize_spoken_text_keeps_danish_letters_and_normalizes_spacing():
    from zeeguu.core.verbal_flashcards.text_normalization import sanitize_spoken_text

    sanitized = sanitize_spoken_text("  MåDér!!!\n  er\t'FÅR'?  ", language_code="da")

    assert sanitized == "mådér er 'får'"


def test_canonical_danish_form_normalizes_to_stable_danish_spellings():
    from zeeguu.core.verbal_flashcards.text_normalization import canonical_danish_form

    assert canonical_danish_form("Maade") == "måde"
    assert canonical_danish_form("OeL") == "øl"
    assert canonical_danish_form("hvad") == "hvad"


def test_asr_tolerant_danish_form_folds_danish_letters_for_transcript_matching():
    from zeeguu.core.verbal_flashcards.text_normalization import (
        asr_tolerant_danish_form,
    )

    assert asr_tolerant_danish_form("træ") == "tre"
    assert asr_tolerant_danish_form("måde") == "made"
    assert asr_tolerant_danish_form("øl") == "ol"
    assert asr_tolerant_danish_form("hvad") == "va"


def test_normalizer_registry_raises_for_unknown_languages():
    from zeeguu.core.verbal_flashcards.text_normalization import (
        UnsupportedLanguageError,
        normalizer_for,
    )

    assert normalizer_for("da").asr_tolerant_form("træ") == "tre"
    assert normalizer_for("da-DK").asr_tolerant_form("hvad") == "va"

    with pytest.raises(UnsupportedLanguageError):
        normalizer_for("de")


def test_score_word_match_accepts_common_danish_asr_variants():
    from zeeguu.core.verbal_flashcards.fuzzy_match import score_word_match

    aa_variant = score_word_match("maade", "måde", language_code="da")
    asr_variant = score_word_match("tre", "træ", language_code="da")

    assert aa_variant["isMatch"] is True
    assert aa_variant["matchType"] == "normalized_exact"
    assert asr_variant["isMatch"] is True
    assert asr_variant["matchType"] == "normalized_exact"


@pytest.mark.parametrize(
    "user_word, expected_word",
    [
        ("hat", "kat"),
        ("hond", "hund"),
        ("pange", "penge"),
    ],
)
def test_score_word_match_accepts_one_optimal_string_alignment_edit(
    user_word,
    expected_word,
):
    from zeeguu.core.verbal_flashcards.fuzzy_match import score_word_match

    result = score_word_match(user_word, expected_word, language_code="da")

    assert result["isMatch"] is True
    assert result["matchType"] == "fuzzy"
    assert result["optimalStringAlignmentDistance"] == 1
    assert result["allowedOptimalStringAlignmentDistance"] == 1
    assert result["jaroWinkler"] > 0


@pytest.mark.parametrize(
    "user_word, expected_word",
    [
        ("hot", "kat"),
        ("hd", "hund"),
        ("pen", "penge"),
    ],
)
def test_score_word_match_rejects_multiple_optimal_string_alignment_edits(
    user_word,
    expected_word,
):
    from zeeguu.core.verbal_flashcards.fuzzy_match import score_word_match

    result = score_word_match(user_word, expected_word, language_code="da")

    assert result["isMatch"] is False
    assert result["matchType"] == "close"
    assert result["optimalStringAlignmentDistance"] > 1
    assert result["allowedOptimalStringAlignmentDistance"] == 1


def test_score_word_match_requires_exact_match_for_two_letter_words():
    from zeeguu.core.verbal_flashcards.fuzzy_match import score_word_match

    result = score_word_match("og", "ok", language_code="da")

    assert result["isMatch"] is False
    assert result["optimalStringAlignmentDistance"] == 1
    assert result["allowedOptimalStringAlignmentDistance"] == 0


def test_calculate_accuracy_ignores_word_order_and_matches_fuzzily():
    from zeeguu.core.verbal_flashcards.fuzzy_match import calculate_accuracy

    result = calculate_accuracy("hund stor", "stor hund", language_code="da")

    assert result["isAccepted"] is True
    assert result["acceptedWordCount"] == 2
    assert result["acceptedAccuracy"] == 100
    assert result["accuracy"] == 100
    assert result["feedback"] == "Success"


def test_calculate_accuracy_marks_close_but_incorrect_words():
    from zeeguu.core.verbal_flashcards.fuzzy_match import calculate_accuracy

    result = calculate_accuracy("sok kat", "bog kat", language_code="da")

    assert result["isAccepted"] is False
    assert result["acceptedWordCount"] == 1
    assert result["feedback"] == "Very close, try again"
    assert result["wordMatches"][0]["word"] == "bog"
    assert result["wordMatches"][0]["isCorrect"] is False
    assert result["wordMatches"][0]["isClose"] is False


def test_calculate_accuracy_says_when_nothing_was_caught():
    from zeeguu.core.verbal_flashcards.fuzzy_match import calculate_accuracy

    result = calculate_accuracy("zzz yyy", "stor hund", language_code="da")

    assert result["isAccepted"] is False
    assert result["acceptedWordCount"] == 0
    assert result["feedback"] == "Didn't catch that, try again"


def test_check_pronunciation_requires_expected_text(client):
    _prepare_bookmark_support()

    response = client.client.post(
        client.append_session("/verbal_flashcards/check_pronunciation"),
        json={"user_speech": "hej"},
    )

    assert response.status_code == 400
    assert b"expected_text is required" in response.data


def test_check_pronunciation_accepts_empty_speech_as_not_caught(client):
    _prepare_bookmark_support()

    response = client.post(
        "/verbal_flashcards/check_pronunciation",
        json={"user_speech": "", "expected_text": "stor hund", "language_code": "da"},
    )

    assert response["isAccepted"] is False
    assert response["acceptedWordCount"] == 0
    assert response["feedback"] == "Didn't catch that, try again"


def test_check_pronunciation_returns_accuracy_analysis(client):
    _prepare_bookmark_support()

    response = client.post(
        "/verbal_flashcards/check_pronunciation",
        json={"user_speech": "tre", "expected_text": "tr\u00e6", "language_code": "da"},
    )

    assert response["isAccepted"] is True
    assert response["acceptedWordCount"] == 1
    assert response["wordMatches"][0]["matchType"] == "normalized_exact"


def test_check_pronunciation_accepts_database_answer_variant_for_same_prompt(client):
    _prepare_bookmark_support()
    _set_client_learned_language(client, "da")

    selected_bookmark = _create_level_3_flashcard(
        client,
        word="landet",
        translation="country",
        from_lang="da",
    )
    selected_bookmark_id = str(selected_bookmark.id)
    _create_level_3_flashcard(
        client,
        word="land",
        translation="country",
        from_lang="da",
    )

    response = client.post(
        "/verbal_flashcards/check_pronunciation",
        json={
            "flashcard_id": selected_bookmark_id,
            "user_speech": "land",
            "expected_text": "landet",
        },
    )

    assert response["isAccepted"] is True
    assert response["acceptedAccuracy"] == 100
    assert response["matchedExpectedText"] == "land"
    assert response["expectedTextVariants"] == ["landet", "land"]


def test_parse_asr_language_overrides_supports_multiple_language_entries():
    from zeeguu.core.audio_lessons.asr_service_client import parse_asr_language_overrides

    mapping = parse_asr_language_overrides(
        "da=http://asr-da, de=http://asr-de;fr=http://asr-fr"
    )

    assert mapping == {
        "da": "http://asr-da",
        "de": "http://asr-de",
        "fr": "http://asr-fr",
    }


def test_asr_service_url_has_no_production_localhost_fallback():
    with _asr_service_client_loaded_with_env() as asr_service_client:
        assert asr_service_client.ASR_SERVICE_URL is None
        assert asr_service_client.ASR_LANGUAGE_OVERRIDE_MAP == {}
        assert asr_service_client.configured_asr_service_urls() == {}


def test_asr_service_url_uses_localhost_fallback_when_flask_debug_is_enabled():
    with _asr_service_client_loaded_with_env(
        flask_debug="1",
    ) as asr_service_client:
        assert asr_service_client.ASR_SERVICE_URL == "http://127.0.0.1:5002"
        assert asr_service_client.ASR_LANGUAGE_OVERRIDE_MAP == {}
        assert asr_service_client.configured_asr_service_urls() == {
            "*": "http://127.0.0.1:5002"
        }


def test_get_asr_service_url_uses_common_backend_and_language_overrides():
    with _asr_service_client_loaded_with_env(
        asr_service_url="http://asr",
        asr_language_overrides="da=http://asr-da",
    ) as asr_service_client:
        assert asr_service_client.get_asr_service_url("da") == "http://asr-da"
        assert asr_service_client.get_asr_service_url("de") == "http://asr"
        assert asr_service_client.get_asr_service_url(None) == "http://asr"


def test_get_asr_service_url_keeps_explicit_empty_override_map():
    with _asr_service_client_loaded_with_env(
        asr_service_url="http://asr",
        asr_language_overrides="da=http://asr-da",
    ) as asr_service_client:
        assert (
            asr_service_client.get_asr_service_url(
                "da",
                service_url="http://asr",
                language_overrides={},
            )
            == "http://asr"
        )


def test_transcribe_endpoint_returns_transcription(client, monkeypatch):
    monkeypatch.setattr(
        "zeeguu.api.endpoints.verbal_flashcards.transcribe_audio",
        lambda audio_file, language_code=None: "hej",
    )

    response = client.client.post(
        client.append_session("/verbal_flashcards/transcribe"),
        data={"file": (io.BytesIO(b"fake audio"), "sample.wav")},
        content_type="multipart/form-data",
    )

    data = response.get_json()

    assert response.status_code == 200
    assert data["transcription"] == "hej"
    assert "flashcard" not in data


def test_transcribe_endpoint_checks_feature_gate_before_audio_validation(client, monkeypatch):
    monkeypatch.setattr(
        "zeeguu.api.endpoints.verbal_flashcards.is_feature_enabled_for_user",
        lambda feature_name, user: False,
    )

    response = client.client.post(client.append_session("/verbal_flashcards/transcribe"))

    assert response.status_code == 404
    assert b"Verbal flashcards are not enabled for this user" in response.data


def test_transcribe_endpoint_rejects_large_audio_upload(client, monkeypatch):
    monkeypatch.setattr(
        "zeeguu.api.endpoints.verbal_flashcards.MAX_VERBAL_FLASHCARD_AUDIO_BYTES",
        512,
    )

    def fail_if_called(audio_file, language_code=None):
        raise AssertionError("transcribe_audio should not run for oversized uploads")

    monkeypatch.setattr(
        "zeeguu.api.endpoints.verbal_flashcards.transcribe_audio",
        fail_if_called,
    )

    response = client.client.post(
        client.append_session("/verbal_flashcards/transcribe"),
        data={"file": (io.BytesIO(b"x" * 1024), "sample.wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert b"Transcription endpoint rejected large audio upload" in response.data


def test_transcribe_audio_routes_to_language_worker(monkeypatch):
    from zeeguu.api.endpoints import verbal_flashcards

    captured = {}

    def fake_transcribe_with_asr_worker(
        audio_bytes,
        filename,
        content_type,
        language_code,
        service_url=None,
        language_overrides=None,
        timeout=None,
    ):
        captured["audio_bytes"] = audio_bytes
        captured["filename"] = filename
        captured["content_type"] = content_type
        captured["language_code"] = language_code
        return {"transcription": "hej"}

    monkeypatch.setattr(
        verbal_flashcards,
        "transcribe_with_asr_worker",
        fake_transcribe_with_asr_worker,
    )

    audio_file = FileStorage(
        stream=io.BytesIO(b"audio-bytes"),
        filename="sample.webm",
        content_type="audio/webm",
    )

    result = verbal_flashcards.transcribe_audio(
        audio_file,
        language_code="da",
    )

    assert result == "hej"
    assert captured["audio_bytes"] == b"audio-bytes"
    assert captured["filename"] == "sample.webm"
    assert captured["content_type"] == "audio/webm"
    assert captured["language_code"] == "da"


def test_transcribe_audio_rejects_file_that_exceeds_read_limit(monkeypatch):
    from zeeguu.api.endpoints import verbal_flashcards

    monkeypatch.setattr(verbal_flashcards, "MAX_VERBAL_FLASHCARD_AUDIO_BYTES", 5)

    audio_file = FileStorage(
        stream=io.BytesIO(b"123456"),
        filename="sample.webm",
        content_type="audio/webm",
    )

    with pytest.raises(verbal_flashcards.VerbalFlashcardAudioTooLarge):
        verbal_flashcards.transcribe_audio(audio_file, language_code="da")


def test_transcribe_endpoint_returns_503_when_worker_is_not_configured(client, monkeypatch):
    from zeeguu.api.endpoints import verbal_flashcards

    def raise_not_configured(audio_file, language_code=None):
        raise verbal_flashcards.ASRServiceNotConfigured(
            "No ASR worker configured for language 'de'"
        )

    monkeypatch.setattr(
        "zeeguu.api.endpoints.verbal_flashcards.transcribe_audio",
        raise_not_configured,
    )

    response = client.client.post(
        client.append_session("/verbal_flashcards/transcribe"),
        data={"file": (io.BytesIO(b"fake audio"), "sample.wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert b"Transcription endpoint not configured" in response.data


def test_verbal_flashcards_submit_reports_exercise_outcome(client):
    _prepare_bookmark_support()
    _set_client_learned_language(client, "da")

    bookmark_id = add_one_bookmark(client)

    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.db import db
    from zeeguu.core.model.exercise import Exercise

    bookmark = Bookmark.find(bookmark_id)
    bookmark.user_word.level = 3
    db.session.commit()

    response = client.post(
        "/verbal_flashcards/submit",
        json={
            "flashcard_id": str(bookmark_id),
            "user_answer": bookmark.user_word.meaning.origin.content,
            "is_correct": True,
            "answer_source": "speech",
            "response_time_ms": 1500,
        },
    )

    assert response["success"] is True
    assert response["flashcard_id"] == str(bookmark_id)
    assert response["is_correct"] is True
    assert response["exercise_outcome"] == "C"

    exercise = Exercise.query.order_by(Exercise.id.desc()).first()
    assert exercise.user_word_id == bookmark.user_word_id
    assert exercise.source.source == "Verbal Flashcards"
    assert exercise.outcome.outcome == "C"
    assert exercise.solving_speed == 1500


def test_submit_uses_fuzzy_acceptance_to_override_is_correct(client):
    _prepare_bookmark_support()
    _set_client_learned_language(client, "da")

    bookmark_id = add_one_bookmark(client)
    _set_bookmark_level(bookmark_id, 3)

    response = client.post(
        "/verbal_flashcards/submit",
        json={
            "flashcard_id": str(bookmark_id),
            "user_answer": "hintar",
            "is_correct": False,
            "answer_source": "speech",
            "response_time_ms": "2000",
        },
    )

    assert response["success"] is True
    assert response["is_correct"] is True
    assert response["exercise_outcome"] == "C"
    assert response["accuracy_analysis"]["isAccepted"] is True
    assert response["accuracy_analysis"]["wordMatches"][0]["matchType"] in {"fuzzy", "normalized_exact"}
    assert response["flashcard_id"] == str(bookmark_id)


def test_submit_accepts_database_answer_variant_for_same_prompt(client):
    _prepare_bookmark_support()
    _set_client_learned_language(client, "da")

    selected_bookmark = _create_level_3_flashcard(
        client,
        word="landet",
        translation="country",
        from_lang="da",
    )
    selected_bookmark_id = str(selected_bookmark.id)
    _create_level_3_flashcard(
        client,
        word="land",
        translation="country",
        from_lang="da",
    )

    response = client.post(
        "/verbal_flashcards/submit",
        json={
            "flashcard_id": selected_bookmark_id,
            "user_answer": "land",
            "is_correct": False,
            "answer_source": "speech",
        },
    )

    assert response["success"] is True
    assert response["is_correct"] is True
    assert response["exercise_outcome"] == "C"
    assert response["accuracy_analysis"]["matchedExpectedText"] == "land"


def test_submit_uses_direct_bookmark_lookup_not_live_flashcard_collection(client, monkeypatch):
    _prepare_bookmark_support()
    _set_client_learned_language(client, "da")

    bookmark_id = add_one_bookmark(client)
    bookmark = _set_bookmark_level(bookmark_id, 3)

    monkeypatch.setattr(
        "zeeguu.core.verbal_flashcards.flashcard_selection.get_flashcard_collection",
        lambda user: [],
    )

    response = client.post(
        "/verbal_flashcards/submit",
        json={
            "flashcard_id": str(bookmark_id),
            "user_answer": bookmark.user_word.meaning.origin.content,
            "is_correct": True,
            "answer_source": "speech",
        },
    )

    assert response["success"] is True
    assert response["flashcard_id"] == str(bookmark_id)
    assert response["is_correct"] is True


def test_submit_rejects_non_integer_session_id(client):
    _prepare_bookmark_support()

    bookmark_id = add_one_bookmark(client)
    _set_bookmark_level(bookmark_id, 3)

    response = client.client.post(
        client.append_session("/verbal_flashcards/submit"),
        json={
            "flashcard_id": str(bookmark_id),
            "user_answer": "hinter",
            "is_correct": True,
            "session_id": "abc",
        },
    )

    assert response.status_code == 400
    assert b"session_id must be an integer" in response.data


def test_submit_coerces_invalid_response_time_to_zero(client):
    _prepare_bookmark_support()
    _set_client_learned_language(client, "da")

    bookmark_id = add_one_bookmark(client)

    from zeeguu.core.model.exercise import Exercise

    bookmark = _set_bookmark_level(bookmark_id, 3)

    response = client.post(
        "/verbal_flashcards/submit",
        json={
            "flashcard_id": str(bookmark_id),
            "user_answer": bookmark.user_word.meaning.origin.content,
            "is_correct": True,
            "response_time_ms": "not-a-number",
        },
    )

    exercise = Exercise.query.order_by(Exercise.id.desc()).first()

    assert response["success"] is True
    assert exercise.solving_speed == 0


def test_submit_rejects_lower_level_flashcard_by_default(client, monkeypatch):
    monkeypatch.delenv("VERBAL_FLASHCARDS_REQUIRE_LEVEL_3", raising=False)
    _prepare_bookmark_support()

    bookmark_id = add_one_bookmark(client)
    bookmark = _set_bookmark_level(bookmark_id, 1)

    response = client.client.post(
        client.append_session("/verbal_flashcards/submit"),
        json={
            "flashcard_id": str(bookmark_id),
            "user_answer": bookmark.user_word.meaning.origin.content,
            "is_correct": True,
        },
    )

    assert response.status_code == 404
    assert b"Flashcard not found" in response.data


def test_submit_accepts_lower_level_flashcard_during_experiment(client, monkeypatch):
    monkeypatch.setenv("VERBAL_FLASHCARDS_REQUIRE_LEVEL_3", "false")
    _prepare_bookmark_support()
    _set_client_learned_language(client, "da")

    bookmark_id = add_one_bookmark(client)
    bookmark = _set_bookmark_level(bookmark_id, 1)

    response = client.post(
        "/verbal_flashcards/submit",
        json={
            "flashcard_id": str(bookmark_id),
            "user_answer": bookmark.user_word.meaning.origin.content,
            "is_correct": True,
        },
    )

    assert response["success"] is True
    assert response["flashcard_id"] == str(bookmark_id)
