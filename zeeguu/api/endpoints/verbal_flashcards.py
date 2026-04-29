import traceback
import flask
import os
from flask import request

from zeeguu.core.model.user import User
from zeeguu.core.audio_lessons.asr_service_client import (
    ASRServiceNotConfigured,
    ASRServiceRequestError,
    transcribe_with_asr_worker,
)
from zeeguu.core.user_feature_toggles import is_feature_enabled_for_user
from zeeguu.core.verbal_flashcards.flashcard_selection import get_flashcard_collection
from zeeguu.core.verbal_flashcards.fuzzy_match import calculate_accuracy
from zeeguu.core.verbal_flashcards.submission import record_flashcard_answer
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from . import api, db_session
from zeeguu.logging import log

DEFAULT_FLASHCARD_LIMIT = 50
DEFAULT_FLASHCARD_OFFSET = 0
DEFAULT_MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_VERBAL_FLASHCARD_AUDIO_BYTES = int(
    os.environ.get("VERBAL_FLASHCARD_MAX_AUDIO_BYTES", DEFAULT_MAX_AUDIO_BYTES)
)


class VerbalFlashcardAudioTooLarge(ValueError):
    pass


def _verbal_flashcards_unavailable_response():
    return json_result({"error": "Verbal flashcards are not enabled for this user"}), 404


def _ensure_verbal_flashcards_enabled(user):
    if is_feature_enabled_for_user("verbal_flashcards", user):
        return None
    return _verbal_flashcards_unavailable_response()


def _current_verbal_flashcards_user():
    user = User.find_by_id(flask.g.user_id)
    return user, _ensure_verbal_flashcards_enabled(user)


def _coerce_int(value, default=0, minimum=None):
    try:
        coerced_value = int(value)
    except (TypeError, ValueError):
        coerced_value = default

    if minimum is not None:
        return max(minimum, coerced_value)

    return coerced_value


def _parse_optional_session_id(value):
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("session_id must be an integer")


def _raise_if_audio_too_large(size):
    if size is not None and size > MAX_VERBAL_FLASHCARD_AUDIO_BYTES:
        raise VerbalFlashcardAudioTooLarge(
            "Audio upload is too large. "
            f"Maximum size is {MAX_VERBAL_FLASHCARD_AUDIO_BYTES} bytes."
        )


def _ensure_request_audio_size_is_allowed():
    _raise_if_audio_too_large(request.content_length)


def _read_audio_file_with_size_limit(audio_file):
    audio_bytes = audio_file.read(MAX_VERBAL_FLASHCARD_AUDIO_BYTES + 1)
    _raise_if_audio_too_large(len(audio_bytes))
    return audio_bytes


def transcribe_audio(audio_file, language_code=None):
    """
    Transcribe audio by routing the request to the dedicated ASR worker that
    owns the model for the user's learned language.
    """
    audio_bytes = _read_audio_file_with_size_limit(audio_file)
    transcription_result = transcribe_with_asr_worker(
        audio_bytes,
        getattr(audio_file, "filename", None),
        getattr(audio_file, "content_type", None),
        language_code,
    )
    return transcription_result.get("transcription", "")


# ====================================
# API Endpoints
# ====================================

@api.route("/verbal_flashcards/transcribe", methods=["POST"])
@cross_domain
@requires_session
def transcribe_audio_endpoint():
    """
    Transcribe an audio recording for a verbal flashcard exercise.
    
    Expected form data:
    - file: audio file (required)
    
    Returns:
    {
        "transcription": "transcribed text"
    }
    """
    try:
        user, feature_gate = _current_verbal_flashcards_user()
        if feature_gate:
            return feature_gate

        _ensure_request_audio_size_is_allowed()

        if "file" not in request.files:
            return json_result({"error": "No audio file provided"}), 400

        audio_file = request.files["file"]
        if audio_file.filename == "":
            return json_result({"error": "Empty filename"}), 400

        learned_language_code = user.learned_language.code if user.learned_language else None

        transcription = transcribe_audio(
            audio_file,
            language_code=learned_language_code,
        )

        log(f"User {user.id} transcribed audio")

        return json_result({
            "success": True,
            "transcription": transcription,
        })

    except ASRServiceNotConfigured as e:
        log(f"Transcription endpoint not configured: {e}")
        return json_result({"error": "Transcription endpoint not configured"}), 503
    except ASRServiceRequestError as e:
        log(f"Transcription endpoint worker failure: {e}")
        return json_result({"error": "Transcription endpoint worker failure"}), 502
    except VerbalFlashcardAudioTooLarge as e:
        log(f"Transcription endpoint rejected large audio upload: {e}")
        return json_result({"error": "Transcription endpoint rejected large audio upload"}), 413
    except Exception as e:
        log(f"Transcription endpoint error: {e}")
        traceback.print_exc()
        return json_result({"error": "Transcription endpoint error"}), 500


@api.route("/verbal_flashcards", methods=["GET"])
@cross_domain
@requires_session
def get_flashcards():
    """
    Get flashcards.
    
    Query parameters:
    - limit: max number of cards to return (optional, default 50)
    - offset: pagination offset (optional, default 0)
    
    Returns list of flashcards.
    """
    try:
        limit = _coerce_int(
            request.args.get("limit"),
            DEFAULT_FLASHCARD_LIMIT,
            minimum=0,
        )
        offset = _coerce_int(
            request.args.get("offset"),
            DEFAULT_FLASHCARD_OFFSET,
            minimum=0,
        )

        user, feature_gate = _current_verbal_flashcards_user()
        if feature_gate:
            return feature_gate
        flashcards = get_flashcard_collection(user)

        total = len(flashcards)
        paginated = flashcards[offset:offset + limit]

        log(f"User {user.id} requested flashcards")

        return json_result({
            "flashcards": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    except Exception as e:
        log(f"Get flashcards error: {e}")
        traceback.print_exc()
        return json_result({"error": "Get flashcards error"}), 500


@api.route("/verbal_flashcards/submit", methods=["POST"])
@cross_domain
@requires_session
def submit_answer():
    """
    Submit an answer for a flashcard and record performance.
    
    Expected JSON body:
    {
        "flashcard_id": "1",
        "user_answer": "transcribed text or typed answer",
        "is_correct": true/false,
        "answer_source": "speech|typing",
        "response_time_ms": 5000,
        "session_id": 123
    }
    
    Returns updated user progress and accuracy analysis.
    """
    try:
        user, feature_gate = _current_verbal_flashcards_user()
        if feature_gate:
            return feature_gate

        data = request.get_json()
        if not data:
            return json_result({"error": "JSON body required"}), 400

        flashcard_id = str(data.get("flashcard_id")) if data.get("flashcard_id") is not None else None
        user_answer = data.get("user_answer", "")
        is_correct = data.get("is_correct")
        answer_source = data.get("answer_source", "unknown")
        response_time = data.get("response_time_ms", 0)
        session_id = data.get("session_id")

        if not flashcard_id or is_correct is None:
            return json_result({"error": "flashcard_id and is_correct are required"}), 400

        learned_language_code = user.learned_language.code if user.learned_language else None

        try:
            session_id = _parse_optional_session_id(session_id)
        except ValueError as exc:
            return json_result({"error": str(exc)}), 400

        response_time = _coerce_int(response_time, minimum=0)

        response_data = record_flashcard_answer(
            db_session,
            user,
            flashcard_id,
            user_answer,
            is_correct,
            answer_source,
            response_time,
            session_id,
            language_code=learned_language_code,
        )
        if not response_data:
            return json_result({"error": "Flashcard not found"}), 404

        log(
            f"User {user.id} answered flashcard {flashcard_id}: "
            f"correct={response_data['is_correct']}, source={answer_source}, "
            f"time={response_time}ms, answer='{user_answer}'"
        )

        return json_result(response_data)

    except Exception as e:
        log(f"Submit answer error: {e}")
        traceback.print_exc()
        return json_result({"error": "Submit answer error"}), 500


@api.route("/verbal_flashcards/check_pronunciation", methods=["POST"])
@cross_domain
@requires_session
def check_pronunciation():
    """
    Check pronunciation of user's speech against expected text.
    Returns accuracy analysis without storing progress.
    
    Expected JSON body:
    {
        "user_speech": "transcribed text",
        "expected_text": "expected phrase"
    }
    """
    try:
        user, feature_gate = _current_verbal_flashcards_user()
        if feature_gate:
            return feature_gate

        data = request.get_json()
        if not data:
            return json_result({"error": "JSON body required"}), 400

        user_speech = data.get("user_speech", "")
        expected_text = data.get("expected_text", "")
        language_code = (
            data.get("language_code")
            or (user.learned_language.code if user.learned_language else None)
        )

        if not user_speech or not expected_text:
            return json_result({"error": "user_speech and expected_text are required"}), 400

        accuracy_analysis = calculate_accuracy(
            user_speech,
            expected_text,
            language_code=language_code,
        )

        return json_result(accuracy_analysis)

    except Exception as e:
        log(f"Check pronunciation error: {e}")
        traceback.print_exc()
        return json_result({"error": "Check pronunciation error"}), 500
