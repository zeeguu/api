"""
Dedicated ASR worker microservice.

The main API proxies verbal-flashcard transcription requests here based on the
user's learned language. The container is addressed as a generic ASR endpoint
from Docker, even while the current deployment only loads the Danish model.
"""

import io
import logging
import os
import tempfile

from flask import Flask, jsonify, request


logger = logging.getLogger(__name__)

ASR_LANGUAGE_CODE = os.environ.get("ASR_LANGUAGE_CODE", "da").casefold()
ASR_SUPPORTED_LANGUAGES = {
    code.strip().casefold()
    for code in os.environ.get("ASR_SUPPORTED_LANGUAGES", ASR_LANGUAGE_CODE).split(",")
    if code.strip()
}
ASR_SUPPORTS_ALL_LANGUAGES = "*" in ASR_SUPPORTED_LANGUAGES
ASR_MODEL_NAME = os.environ.get(
    "ASR_MODEL_NAME",
    "nvidia/parakeet-rnnt-110m-da-dk",
)
ASR_WORKER_NAME = os.environ.get(
    "ASR_WORKER_NAME",
    f"asr-{ASR_LANGUAGE_CODE}",
)
DEFAULT_MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_ASR_AUDIO_BYTES = int(
    os.environ.get(
        "ASR_MAX_AUDIO_BYTES",
        os.environ.get("VERBAL_FLASHCARD_MAX_AUDIO_BYTES", DEFAULT_MAX_AUDIO_BYTES),
    )
)
ASR_LEADING_SILENCE_MS = int(os.environ.get("ASR_LEADING_SILENCE_MS", "250"))
ASR_TRAILING_SILENCE_MS = int(os.environ.get("ASR_TRAILING_SILENCE_MS", "250"))


class ASRAudioTooLarge(ValueError):
    pass


class ASRModelUnavailable(RuntimeError):
    pass


def raise_if_audio_too_large(size):
    if size is not None and size > MAX_ASR_AUDIO_BYTES:
        raise ASRAudioTooLarge(
            f"Audio upload is too large. Maximum size is {MAX_ASR_AUDIO_BYTES} bytes."
        )


def extract_transcription(transcript):
    """
    NeMo 2.7.3 with nvidia/parakeet-rnnt-110m-da-dk returns list[Hypothesis].

    The Hypothesis object exposes the decoded transcription as `.text`. If a
    future NeMo/model upgrade changes this shape, fail loudly.
    """
    if not isinstance(transcript, list) or len(transcript) != 1:
        raise TypeError(
            "Unexpected transcription output shape: "
            f"expected one Hypothesis in a list, got {type(transcript).__name__}"
        )

    hypothesis = transcript[0]
    if not hasattr(hypothesis, "text") or not isinstance(hypothesis.text, str):
        raise TypeError(
            "Unexpected transcription item shape: "
            f"expected Hypothesis with string .text, got {type(hypothesis).__name__}"
        )

    return hypothesis.text


def supports_language(language_code):
    if not language_code:
        return True
    if ASR_SUPPORTS_ALL_LANGUAGES:
        return True
    return str(language_code).casefold() in ASR_SUPPORTED_LANGUAGES


def supported_languages_for_response():
    if ASR_SUPPORTS_ALL_LANGUAGES:
        return ["*"]
    return sorted(ASR_SUPPORTED_LANGUAGES)


def add_asr_padding(audio):
    """
    Add a small silence cushion around very short learner recordings.

    Short one-word clips can begin at the exact first phoneme, which is brittle
    for browser microphones and autoregressive ASR. Silence padding gives the
    model stable acoustic lead-in/out without injecting fake spoken tokens.
    """
    leading_ms = max(0, ASR_LEADING_SILENCE_MS)
    trailing_ms = max(0, ASR_TRAILING_SILENCE_MS)

    if leading_ms:
        leading_silence = (
            AudioSegment.silent(duration=leading_ms, frame_rate=audio.frame_rate)
            .set_channels(audio.channels)
            .set_sample_width(audio.sample_width)
        )
        audio = leading_silence + audio

    if trailing_ms:
        trailing_silence = (
            AudioSegment.silent(duration=trailing_ms, frame_rate=audio.frame_rate)
            .set_channels(audio.channels)
            .set_sample_width(audio.sample_width)
        )
        audio = audio + trailing_silence

    return audio


try:
    import nemo.collections.asr as nemo_asr
    from pydub import AudioSegment

    ASR_AVAILABLE = True
    asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=ASR_MODEL_NAME)
    print(
        f"Loaded ASR worker {ASR_WORKER_NAME} for "
        f"{', '.join(supported_languages_for_response())} "
        f"with model {ASR_MODEL_NAME}"
    )
except ImportError as exc:
    ASR_AVAILABLE = False
    asr_model = None
    print(f"ASR worker dependencies unavailable: {exc}")
except Exception as exc:
    ASR_AVAILABLE = False
    asr_model = None
    print(f"Failed to load ASR worker model {ASR_MODEL_NAME}: {exc}")


def transcribe_audio_file(audio_storage, requested_language_code=None):
    temp_path = None

    if not supports_language(requested_language_code):
        raise ValueError(
            f"Worker {ASR_WORKER_NAME} does not support '{requested_language_code}'"
        )

    try:
        audio_bytes = audio_storage.read(MAX_ASR_AUDIO_BYTES + 1)
        raise_if_audio_too_large(len(audio_bytes))

        if not ASR_AVAILABLE or asr_model is None:
            raise ASRModelUnavailable("ASR model is not available in this worker")

        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio = add_asr_padding(audio)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
            audio.export(temp_path, format="wav")

        transcript = asr_model.transcribe([temp_path])
        transcription = extract_transcription(transcript)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
    return transcription


app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    payload = {
        "status": "ok" if ASR_AVAILABLE and asr_model is not None else "degraded",
        "worker_name": ASR_WORKER_NAME,
        "worker_languages": supported_languages_for_response(),
        "model_loaded": asr_model is not None,
    }
    status_code = 200 if payload["status"] == "ok" else 503
    return jsonify(payload), status_code


@app.route("/transcribe", methods=["POST"])
def transcribe():
    try:
        raise_if_audio_too_large(request.content_length)
    except ASRAudioTooLarge as exc:
        logger.info("ASR request rejected because audio was too large: %s", exc)
        return jsonify({"error": "Audio upload is too large"}), 413

    if "file" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["file"]
    if audio_file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    requested_language_code = request.form.get("language_code")

    try:
        if not ASR_AVAILABLE or asr_model is None:
            raise ASRModelUnavailable("ASR model is not available in this worker")

        transcription = transcribe_audio_file(
            audio_file,
            requested_language_code=requested_language_code,
        )
        return jsonify(
            {
                "success": True,
                "transcription": transcription,
            }
        )
    except ASRAudioTooLarge as exc:
        logger.info("ASR request rejected because audio was too large: %s", exc)
        return jsonify({"error": "Audio upload is too large"}), 413
    except ASRModelUnavailable as exc:
        logger.info("ASR model unavailable: %s", exc)
        return jsonify({"error": "ASR model unavailable"}), 503
    except ValueError as exc:
        logger.info("ASR request rejected: %s", exc)
        return jsonify({"error": "ASR request rejected"}), 400
    except Exception:
        logger.exception("ASR transcription failed")
        return jsonify({"error": "ASR transcription failed"}), 500


if __name__ == "__main__":
    # TODO: Temporary local-dev override. Remove this when local ASR no longer
    # needs to run beside `python start.py` on http://127.0.0.1:5002.
    app.run(host="0.0.0.0", port=int(os.environ.get("ASR_SERVICE_PORT", "5002")))
