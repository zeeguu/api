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


def test_health_returns_503_when_model_is_unavailable(monkeypatch):
    monkeypatch.setattr(asr_app, "ASR_AVAILABLE", False)
    monkeypatch.setattr(asr_app, "asr_model", None)

    response = asr_app.app.test_client().get("/health")

    assert response.status_code == 503
    assert response.get_json()["status"] == "degraded"
    assert response.get_json()["model_loaded"] is False


def test_health_returns_200_when_model_is_loaded(monkeypatch):
    monkeypatch.setattr(asr_app, "ASR_AVAILABLE", True)
    monkeypatch.setattr(asr_app, "asr_model", object())

    response = asr_app.app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["model_loaded"] is True
