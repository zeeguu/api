import io
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


def _set_bookmark_level(bookmark_id, level):
    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.db import db

    bookmark = Bookmark.find(bookmark_id)
    bookmark.user_word.level = level
    db.session.commit()
    return bookmark


def _create_level_3_flashcard(client, word="hinter", translation="behind"):
    from zeeguu.core.model.context_identifier import ContextIdentifier
    from zeeguu.core.model.context_type import ContextType
    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.db import db
    from fixtures import create_and_get_article
    from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA

    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    bookmark = client.post(
        "/contribute_translation/de/en",
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


# Disabled intentionally after removing the level-3 gate so participants
# in the experiment still receive verbal flashcards.
# def test_verbal_flashcards_only_returns_level_3_plus_words(client):
#     _prepare_bookmark_support()
#
#     bookmark_id = add_one_bookmark(client)
#     bookmark = _set_bookmark_level(bookmark_id, 2)
#
#     flashcards = client.get("/verbal_flashcards")
#     assert flashcards["total"] == 0
#
#     bookmark = _set_bookmark_level(bookmark_id, 3)
#     expected_prompt = bookmark.user_word.meaning.translation.content
#     expected_answer = bookmark.user_word.meaning.origin.content
#     flashcards = client.get("/verbal_flashcards")
#
#     assert flashcards["total"] == 1
#     assert len(flashcards["flashcards"]) == 1
#     assert flashcards["flashcards"][0]["id"] == str(bookmark_id)
#     assert flashcards["flashcards"][0]["prompt"] == expected_prompt
#     assert flashcards["flashcards"][0]["answer"] == expected_answer


def test_verbal_flashcards_returns_404_when_feature_is_disabled(client, monkeypatch):
    _prepare_bookmark_support()

    monkeypatch.setattr(
        "zeeguu.api.endpoints.verbal_flashcards.is_feature_enabled_for_user",
        lambda feature_name, user: False,
    )

    response = client.client.get(client.append_session("/verbal_flashcards"))

    assert response.status_code == 404
    assert b"Verbal flashcards are not enabled for this user" in response.data


def test_verbal_flashcards_deduplicate_same_origin_word(client):
    _prepare_bookmark_support()

    _create_level_3_flashcard(client, word="hinter", translation="behind")
    _create_level_3_flashcard(client, word="hinter", translation="at the back of")

    flashcards = client.get("/verbal_flashcards")

    assert flashcards["total"] == 1
    assert flashcards["flashcards"][0]["answer"] == "hinter"


def test_verbal_flashcards_paginates_results(client):
    _prepare_bookmark_support()

    _create_level_3_flashcard(client, word="hinter", translation="behind")
    _create_level_3_flashcard(client, word="gehen", translation="go")

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

    sanitized = sanitize_spoken_text("  MåDér!!!\n  er\t'FÅR'?  ")

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


def test_normalizer_registry_defaults_to_danish_until_more_languages_exist():
    from zeeguu.core.verbal_flashcards.text_normalization import normalizer_for

    assert normalizer_for("da").asr_tolerant_form("træ") == "tre"
    assert normalizer_for("da-DK").asr_tolerant_form("hvad") == "va"
    assert normalizer_for("de").asr_tolerant_form("træ") == "tre"


def test_score_word_match_accepts_common_danish_asr_variants():
    from zeeguu.core.verbal_flashcards.fuzzy_match import score_word_match

    aa_variant = score_word_match("maade", "måde")
    asr_variant = score_word_match("tre", "træ")

    assert aa_variant["isMatch"] is True
    assert aa_variant["matchType"] == "normalized_exact"
    assert asr_variant["isMatch"] is True
    assert asr_variant["matchType"] == "normalized_exact"


def test_calculate_accuracy_ignores_word_order_and_matches_fuzzily():
    from zeeguu.core.verbal_flashcards.fuzzy_match import calculate_accuracy

    result = calculate_accuracy("hund stor", "stor hund")

    assert result["isAccepted"] is True
    assert result["acceptedWordCount"] == 2
    assert result["acceptedAccuracy"] == 100
    assert result["accuracy"] == 100


def test_calculate_accuracy_marks_close_but_incorrect_words():
    from zeeguu.core.verbal_flashcards.fuzzy_match import calculate_accuracy

    result = calculate_accuracy("sok kat", "bog kat")

    assert result["isAccepted"] is False
    assert result["acceptedWordCount"] == 1
    assert result["wordMatches"][0]["word"] == "bog"
    assert result["wordMatches"][0]["isCorrect"] is False
    assert result["wordMatches"][0]["isClose"] is False


def test_check_pronunciation_requires_both_fields(client):
    _prepare_bookmark_support()

    response = client.client.post(
        client.append_session("/verbal_flashcards/check_pronunciation"),
        json={"user_speech": "hej"},
    )

    assert response.status_code == 400
    assert b"user_speech and expected_text are required" in response.data


def test_check_pronunciation_returns_accuracy_analysis(client):
    _prepare_bookmark_support()

    response = client.post(
        "/verbal_flashcards/check_pronunciation",
        json={"user_speech": "tre", "expected_text": "tr\u00e6"},
    )

    assert response["isAccepted"] is True
    assert response["acceptedWordCount"] == 1
    assert response["wordMatches"][0]["matchType"] == "normalized_exact"


def test_parse_asr_service_urls_supports_multiple_language_workers():
    from zeeguu.core.audio_lessons.asr_service_client import parse_asr_service_urls

    mapping = parse_asr_service_urls(
        "da=http://asr-da:5002, de=http://asr-de:5002;fr=http://asr-fr:5002"
    )

    assert mapping == {
        "da": "http://asr-da:5002",
        "de": "http://asr-de:5002",
        "fr": "http://asr-fr:5002",
    }


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


# Disabled intentionally while the transcribe endpoint returns normalized
# high-level error messages instead of the previous raw worker text.
# def test_transcribe_endpoint_rejects_large_audio_upload(client, monkeypatch):
#     monkeypatch.setattr(
#         "zeeguu.api.endpoints.verbal_flashcards.MAX_VERBAL_FLASHCARD_AUDIO_BYTES",
#         512,
#     )
#
#     def fail_if_called(audio_file, language_code=None):
#         raise AssertionError("transcribe_audio should not run for oversized uploads")
#
#     monkeypatch.setattr(
#         "zeeguu.api.endpoints.verbal_flashcards.transcribe_audio",
#         fail_if_called,
#     )
#
#     response = client.client.post(
#         client.append_session("/verbal_flashcards/transcribe"),
#         data={"file": (io.BytesIO(b"x" * 1024), "sample.wav")},
#         content_type="multipart/form-data",
#     )
#
#     assert response.status_code == 413
#     assert b"Audio upload is too large" in response.data


def test_transcribe_audio_routes_to_language_worker(monkeypatch):
    from zeeguu.api.endpoints import verbal_flashcards

    captured = {}

    def fake_transcribe_with_asr_worker(
        audio_bytes,
        filename,
        content_type,
        language_code,
        service_url_map=None,
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


# Disabled intentionally while the transcribe endpoint returns normalized
# high-level error messages instead of the previous raw worker text.
# def test_transcribe_endpoint_returns_503_when_worker_is_not_configured(client, monkeypatch):
#     from zeeguu.core.audio_lessons.asr_service_client import ASRServiceNotConfigured
#
#     def raise_not_configured(audio_file, language_code=None):
#         raise ASRServiceNotConfigured("No ASR worker configured for language 'de'")
#
#     monkeypatch.setattr(
#         "zeeguu.api.endpoints.verbal_flashcards.transcribe_audio",
#         raise_not_configured,
#     )
#
#     response = client.client.post(
#         client.append_session("/verbal_flashcards/transcribe"),
#         data={"file": (io.BytesIO(b"fake audio"), "sample.wav")},
#         content_type="multipart/form-data",
#     )
#
#     assert response.status_code == 503
#     assert b"No ASR worker configured for language 'de'" in response.data


def test_verbal_flashcards_submit_reports_exercise_outcome(client):
    _prepare_bookmark_support()

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


def test_submit_uses_direct_bookmark_lookup_not_live_flashcard_collection(client, monkeypatch):
    _prepare_bookmark_support()

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


def test_submit_accepts_lower_level_flashcard_during_experiment(client):
    _prepare_bookmark_support()

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
