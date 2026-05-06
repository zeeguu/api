import pytest

import app as asr_app


class _Hypothesis:
    def __init__(self, text):
        self.text = text


def test_extract_transcription_accepts_pinned_nemo_hypothesis_shape():
    transcript = [_Hypothesis("det var godt")]

    assert asr_app.extract_transcription(transcript) == "det var godt"


def test_extract_transcription_rejects_legacy_tuple_shape():
    transcript = (["det var godt"], [0.99])

    with pytest.raises(TypeError) as exc_info:
        asr_app.extract_transcription(transcript)

    assert "expected one Hypothesis in a list" in str(exc_info.value)


def test_extract_transcription_rejects_string_list_shape():
    transcript = ["det var godt"]

    with pytest.raises(TypeError) as exc_info:
        asr_app.extract_transcription(transcript)

    assert "expected Hypothesis with string .text" in str(exc_info.value)


def test_extract_transcription_rejects_nested_list_shape():
    transcript = [[_Hypothesis("det var godt")]]

    with pytest.raises(TypeError) as exc_info:
        asr_app.extract_transcription(transcript)

    assert "expected Hypothesis with string .text" in str(exc_info.value)


def test_supports_language_uses_worker_supported_languages(monkeypatch):
    monkeypatch.setattr(asr_app, "ASR_SUPPORTS_ALL_LANGUAGES", False)
    monkeypatch.setattr(asr_app, "ASR_SUPPORTED_LANGUAGES", {"da", "de"})

    assert asr_app.supports_language("da") is True
    assert asr_app.supports_language("DE") is True
    assert asr_app.supports_language("fr") is False


def test_supports_language_accepts_any_language_for_multilingual_worker(monkeypatch):
    monkeypatch.setattr(asr_app, "ASR_SUPPORTS_ALL_LANGUAGES", True)

    assert asr_app.supports_language("fr") is True


def test_add_asr_padding_adds_configured_silence(monkeypatch):
    if not hasattr(asr_app, "AudioSegment"):
        pytest.skip("pydub is not available in this environment")

    monkeypatch.setattr(asr_app, "ASR_LEADING_SILENCE_MS", 250)
    monkeypatch.setattr(asr_app, "ASR_TRAILING_SILENCE_MS", 350)

    audio = asr_app.AudioSegment.silent(duration=100, frame_rate=16000).set_channels(1)
    padded = asr_app.add_asr_padding(audio)

    assert len(padded) == 700
    assert padded.frame_rate == 16000
    assert padded.channels == 1


def test_health_returns_503_when_model_is_unavailable(monkeypatch):
    monkeypatch.setattr(asr_app, "ASR_AVAILABLE", False)
    monkeypatch.setattr(asr_app, "asr_model", None)
    monkeypatch.setattr(asr_app, "ASR_SUPPORTS_ALL_LANGUAGES", False)
    monkeypatch.setattr(asr_app, "ASR_SUPPORTED_LANGUAGES", {"da"})

    response = asr_app.app.test_client().get("/health")

    assert response.status_code == 503
    assert response.get_json()["status"] == "degraded"
    assert response.get_json()["model_loaded"] is False
    assert response.get_json()["worker_languages"] == ["da"]


def test_health_returns_200_when_model_is_loaded(monkeypatch):
    monkeypatch.setattr(asr_app, "ASR_AVAILABLE", True)
    monkeypatch.setattr(asr_app, "asr_model", object())

    response = asr_app.app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["model_loaded"] is True
